// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

// These are the core Yearn libraries
import {
    BaseStrategy,
    StrategyParams
} from "@yearnvaults/contracts/BaseStrategy.sol";
import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/math/Math.sol";

import "../interfaces/IMorpho.sol";
import "../interfaces/lens/ILens.sol";

abstract contract MorphoStrategy is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    // Morpho is a contract to handle interaction with the protocol
    IMorpho public immutable morpho;
    // Lens is a contract to fetch data about Morpho protocol
    ILens public immutable lens;
    // poolToken = Morpho Market for want token, address of poolToken
    address public immutable poolToken;
    // Max gas used for matching with p2p deals
    uint256 public maxGasForMatching = 100000;
    string internal strategyName;

    uint256 public minObservationTimeDiff = 1 days;
    uint8 private constant MAX_OBSERVATIONS = 30;
    LiquidityObservation[MAX_OBSERVATIONS] public liquidityObservations;
    // use max value to indicate that observations are not initialized
    uint8 public observationIndex = MAX_OBSERVATIONS;

    struct LiquidityObservation {
        // P2P supply liquidity at the moment of the observation
        uint256 p2p;
        // pool supply liquidity at the moment of the observation
        uint256 pool;
        // the block timestamp of the observation
        uint256 timestamp;
    }

    constructor(
        address _vault,
        address _poolToken,
        string memory _strategyName,
        address _morpho,
        address _lens
    ) public BaseStrategy(_vault) {
        poolToken = _poolToken;
        strategyName = _strategyName;
        lens = ILens(_lens);
        morpho = IMorpho(_morpho);
        want.safeApprove(_morpho, type(uint256).max);
    }

    // ******** BaseStrategy overriden contract function ************

    function name() external view override returns (string memory) {
        return strategyName;
    }

    function estimatedTotalAssets() public view override returns (uint256) {
        return want.balanceOf(address(this)).add(balanceOfPoolToken());
    }

    // NOTE: Return `_profit` which is value generated by all positions, priced in `want`
    // NOTE: Should try to free up at least `_debtOutstanding` of underlying position
    function prepareReturn(uint256 _debtOutstanding)
        internal
        virtual
        override
        returns (
            uint256 _profit,
            uint256 _loss,
            uint256 _debtPayment
        )
    {
        uint256 totalDebt = vault.strategies(address(this)).totalDebt;
        uint256 totalAssetsAfterProfit = estimatedTotalAssets();
        _profit = totalAssetsAfterProfit > totalDebt
            ? totalAssetsAfterProfit.sub(totalDebt)
            : 0;

        (_debtPayment, _loss) = liquidatePosition(
            _debtOutstanding.add(_profit)
        );
        _debtPayment = Math.min(_debtPayment, _debtOutstanding);

        // Net profit and loss calculation
        if (_loss > _profit) {
            _loss = _loss.sub(_profit);
            _profit = 0;
        } else {
            _profit = _profit.sub(_loss);
            _loss = 0;
        }
    }

    // NOTE: Try to adjust positions so that `_debtOutstanding` can be freed up on *next* harvest (not immediately)
    function adjustPosition(uint256 _debtOutstanding) internal override {
        uint256 wantBalance = want.balanceOf(address(this));
        if (wantBalance > _debtOutstanding) {
            morpho.supply(
                poolToken,
                address(this),
                wantBalance.sub(_debtOutstanding),
                maxGasForMatching
            );
        }
        // TODO: see if this is the best place to call update from
        updateLiquidityObservation();
    }

    function liquidatePosition(uint256 _amountNeeded)
        internal
        override
        returns (uint256 _liquidatedAmount, uint256 _loss)
    {
        uint256 wantBalance = want.balanceOf(address(this));
        if (_amountNeeded > wantBalance) {
            _liquidatedAmount = Math.min(
                _amountNeeded.sub(wantBalance),
                balanceOfPoolToken()
            );
            morpho.withdraw(poolToken, _liquidatedAmount);
            _liquidatedAmount = Math.min(
                want.balanceOf(address(this)),
                _amountNeeded
            );
            _loss = _amountNeeded > _liquidatedAmount
                ? _amountNeeded.sub(_liquidatedAmount)
                : 0;
        } else {
            _liquidatedAmount = _amountNeeded;
        }
    }

    function liquidateAllPositions() internal override returns (uint256) {
        uint256 balanceToWithdraw = balanceOfPoolToken();
        if (balanceToWithdraw > 0) {
            morpho.withdraw(poolToken, balanceToWithdraw);
        }
        return want.balanceOf(address(this));
    }

    // NOTE: Can override `tendTrigger` and `harvestTrigger` if necessary
    function prepareMigration(address _newStrategy) internal virtual override {
        liquidateAllPositions();
    }

    function protectedTokens()
        internal
        view
        override
        returns (address[] memory)
    {}

    /**
     * @notice
     *  Provide an accurate conversion from `_amtInWei` (denominated in wei)
     *  to `want` (using the native decimal characteristics of `want`).
     * @dev
     *  Care must be taken when working with decimals to assure that the conversion
     *  is compatible. As an example:
     *
     *      given 1e17 wei (0.1 ETH) as input, and want is USDC (6 decimals),
     *      with USDC/ETH = 1800, this should give back 1800000000 (180 USDC)
     *
     * @param _amtInWei The amount (in wei/1e-18 ETH) to convert to `want`
     * @return The amount in `want` of `_amtInEth` converted to `want`
     **/
    function ethToWant(uint256 _amtInWei)
        public
        view
        virtual
        override
        returns (uint256)
    {
        // TODO create an accurate price oracle
        return _amtInWei;
    }

    /**
     * @notice
     *  Updates the array of Liquidity Observations which stores the P2P and pool liquidity at the current moment.
     *  Update is completed only if minObservationTimeDiff has passed after the last liquidity observation update.
     *  Only supply liquidity is recorded.
     * @dev
     *  History values are recorded in a circular array meaning that the new values will override the oldest value
     *  after the array is full.
     */
    function updateLiquidityObservation() public onlyAuthorized {
        // store liquidity observation only if at least minObservationTimeDiff has passed
        if (
            observationIndex != MAX_OBSERVATIONS &&
            block.timestamp.sub(
                liquidityObservations[observationIndex].timestamp
            ) <
            minObservationTimeDiff
        ) {
            return;
        }

        if (observationIndex >= MAX_OBSERVATIONS - 1) {
            // LiqudityObservations act like a circular array
            observationIndex = 0;
        } else {
            observationIndex++;
        }

        uint256 p2p;
        uint256 pool;
        (, , p2p, , pool, ) = lens.getMainMarketData(poolToken);
        liquidityObservations[observationIndex] = LiquidityObservation({
            p2p: p2p,
            pool: pool,
            timestamp: block.timestamp
        });
    }

    /**
     * @notice
     *  Set the minimum time that must pass before a new liquidity observation is recored.
     * @param _minObservationTimeDiff new minimum time that must pass before liquidity observation record update
     */
    function setMinObservationTimeDiff(uint256 _minObservationTimeDiff)
        external
        onlyAuthorized
    {
        minObservationTimeDiff = _minObservationTimeDiff;
    }

    /**
     * @notice
     *  Set the maximum amount of gas to consume to get matched in peer-to-peer.
     * @dev
     *  This value is needed in morpho supply liquidity calls.
     *  Supplyed liquidity goes to loop with current loans on Compound
     *  and creates a match for p2p deals. The loop starts from bigger liquidity deals.
     * @param _maxGasForMatching new maximum gas value for
     */
    function setMaxGasForMatching(uint256 _maxGasForMatching)
        external
        onlyAuthorized
    {
        maxGasForMatching = _maxGasForMatching;
    }

    // ---------------------- View function ----------------------
    /**
     * @notice
     *  Computes and returns the total amount of underlying ERC20 token a given user has supplied through Morpho
     *  on a given market, taking into account interests accrued.
     * @dev
     *  The value is in `want` precision, decimals so there is no need to convert this value if calculating with `want`.
     * @return _balance of `want` token supplied to Morpho in `want` precision
     */
    function balanceOfPoolToken() public view returns (uint256 _balance) {
        (, , _balance) = lens.getCurrentSupplyBalanceInOf(
            poolToken,
            address(this)
        );
    }

    /**
     * @notice
     *  Computes and returns the total amount of underlying ERC20 token a given user has supplied through Morpho
     *  on a given market, taking into account interests accrued.
     * @return _balanceOnPool balance of pool token provided to pool, underlying protocol
     * @return _balanceInP2P balance provided to P2P deals
     * @return _totalBalance equals to balanceOnPool + balanceInP2P
     */
    function getSupplyBalance()
        public
        view
        returns (
            uint256 _balanceOnPool,
            uint256 _balanceInP2P,
            uint256 _totalBalance
        )
    {
        (_balanceOnPool, _balanceInP2P, _totalBalance) = lens
            .getCurrentSupplyBalanceInOf(poolToken, address(this));
    }

    /**
     * @notice
     *  Gets the current P2P liquditiy for supplied and borrowed amount in Morpho protocol for strategy pool token
     * @return _p2pSupplyAmount supplied amount of pool token in P2P deals
     * @return _p2pBorrowAmount borrowed amount of pool token in P2P deals
     */
    function getCurrentP2PLiquditiy()
        external
        view
        returns (uint256 _p2pSupplyAmount, uint256 _p2pBorrowAmount)
    {
        (, , _p2pSupplyAmount, _p2pBorrowAmount, , ) = lens.getMainMarketData(
            poolToken
        );
    }

    /**
     * @notice
     *  Gets the current pool liquditiy for supplied and borrowed amount in Morpho protocol for strategy pool token.
     *  Pool liquidity is liquidity in underlying protocol, i.e. non P2P deals
     * @return _poolSupplyAmount supplied amount of pool token in pool deals
     * @return _poolBorrowAmount borrowed amount of pool token in pool deals
     */
    function getCurrentPoolLiquditiy()
        external
        view
        returns (uint256 _poolSupplyAmount, uint256 _poolBorrowAmount)
    {
        (, , , , _poolSupplyAmount, _poolBorrowAmount) = lens.getMainMarketData(
            poolToken
        );
    }

    /**
     * @notice
     *  Caluclates the maximum amount that can be supplied to just P2P deals.
     * @return _maxP2PSupply maximum amount that can be supplied to P2P deals
     */
    function calculateMaxP2PSupply()
        external
        view
        returns (uint256 _maxP2PSupply)
    {
        (_maxP2PSupply, , ) = getSupplyBalancesForAmount(type(uint128).max);
    }

    /**
     * @notice
     *  Calculates the difference between the current liquidity, both P2P and pool,
     *  and liquidity that was recorded before number of days.
     *  Days metric is not correct but the response contains timestamp difference for more accurate analysis.
     *  If the value is not recorded for a given input, all output values are 0.
     *  Negative liquidity value indicates that the liquidity has decreased. Only supply liquidity is provided.
     * @dev
     *  Real input metric is not days but a position in array.
     * @param _daysBefore number of days to go back from now to get recorded liquidity data
     * @return _p2pLiquidityDiff difference between the current P2P liquidity and P2P recorded data before
     * @return _poolLiquidityDiff difference between the current pool liquidity and pool recorded data before.
     * Pool liquidity is liquidity that didn't find a match for P2P and is supplied to underlying protocol.
     * @return _timestampDiff difference between the current timestamp and the timestamp of recorded data
     */
    function calculateLiqudityDifference(uint8 _daysBefore)
        external
        view
        returns (
            int256 _p2pLiquidityDiff,
            int256 _poolLiquidityDiff,
            uint256 _timestampDiff
        )
    {
        require(_daysBefore < MAX_OBSERVATIONS, "Max value is 30");
        require(observationIndex != MAX_OBSERVATIONS, "No values");

        uint8 index;
        if (observationIndex >= _daysBefore) {
            index = observationIndex - _daysBefore;
        } else {
            // add MAX_OBSERVATIONS to complete the circle, array data is stored in circular way
            index = observationIndex + MAX_OBSERVATIONS - _daysBefore;
        }

        LiquidityObservation memory liquidityObservation =
            liquidityObservations[index];
        // handle undefined values
        if (liquidityObservation.timestamp == 0) {
            return (0, 0, 0);
        }

        uint256 currentP2p;
        uint256 currentPool;
        // get the current supply liquidity data
        (, , currentP2p, , currentPool, ) = lens.getMainMarketData(poolToken);
        _p2pLiquidityDiff =
            toInt256(currentP2p) -
            toInt256(liquidityObservation.p2p);
        _poolLiquidityDiff =
            toInt256(currentPool) -
            toInt256(liquidityObservation.pool);
        _timestampDiff = block.timestamp - liquidityObservation.timestamp;
    }

    /**
     * @notice
     *  For a given amount of pool tokens it will return balance that will end in P2P deal and balance of pool deal.
     * @param _amount Token amount intended to supply to Morpho protocol
     * @return _balanceInP2P balance that will end up in P2P deals
     * @return _balanceOnPool balance that will end up in pool deal, underlying protocol
     * @return _apr hypothetical supply rate per year experienced by the user on the given market,
     * devide by 10^16 to get a number in percentage
     */
    function getSupplyBalancesForAmount(uint256 _amount)
        public
        view
        virtual
        returns (
            uint256 _balanceInP2P,
            uint256 _balanceOnPool,
            uint256 _apr
        );

    /**
     * @notice
     *  Cast a uint256 to a int256, revert on overflow
     * @param y The uint256 to be casted
     * @return z The casted integer, now type int256
     */
    function toInt256(uint256 y) internal pure returns (int256 z) {
        require(y < 2**255);
        z = int256(y);
    }
}
