// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import "./MorphoStrategy.sol";

contract MorphoCompoundStrategy is MorphoStrategy {
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
            0x8888882f8f843896699869179fB6E4f7e3B58888,
            0x930f1b46e1D081Ec1524efD95752bE3eCe51EF67,
            0xc00e94Cb662C3520282E6f5717214004A7f26888
        )
    {}

    function claimRewardToken() internal override {
        address[] memory pools = new address[](1);
        pools[0] = poolToken;
        if (
            lens.getUserUnclaimedRewards(pools, address(this)) >
            minRewardToClaimOrSell
        ) {
            // claim the underlying pool's rewards, currently COMP token
            morpho.claimRewards(pools, false);
        }
    }
}
