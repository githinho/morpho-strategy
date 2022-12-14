// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import "./MorphoStrategy.sol";

contract MorphoAaveStrategy is MorphoStrategy {
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
}
