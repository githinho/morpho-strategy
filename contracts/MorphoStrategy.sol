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
import "../interfaces/ILens.sol";

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
    address public constant WETH = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;

    // Max gas used for matching with p2p deals
    uint256 public maxGasForMatching = 100000;
    string internal strategyName;

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
}