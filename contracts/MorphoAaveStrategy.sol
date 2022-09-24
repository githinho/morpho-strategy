// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import "./MorphoStrategy.sol";
import "../interfaces/lens/ILensAave.sol";

contract MorphoAaveStrategy is MorphoStrategy {
    // used to downscale APR value to match Compound APR precision
    uint256 private constant COMPOUND_DOWNSCALE = 10**9;

    constructor(
        address _vault,
        address _poolToken,
        string memory _strategyName
    )
        public
        MorphoStrategy(
            _vault,
            _poolToken,
            _strategyName,
            0x777777c9898D384F785Ee44Acfe945efDFf5f3E0,
            0x507fA343d0A90786d86C7cd885f5C49263A91FF4
        )
    {}

    function getNextUserSupplyBalances(uint256 _amount)
        public
        view
        override
        returns (
            uint256 _balanceInP2P,
            uint256 _balanceOnPool,
            uint256 _apr
        )
    {
        uint256 nextSupplyRatePerYear;
        (nextSupplyRatePerYear, _balanceInP2P, _balanceOnPool, ) = ILensAave(
            address(lens)
        )
            .getNextUserSupplyRatePerYear(poolToken, address(this), _amount);
        _apr = nextSupplyRatePerYear.div(COMPOUND_DOWNSCALE);
    }
}
