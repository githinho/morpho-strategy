import brownie
from brownie import Contract, Wei
import pytest


def test_strategy_setup(token, strategy):
    uint256_max = 2**256 - 1
    assert token.allowance(strategy.address, strategy.morpho()) == uint256_max


def test_set_max_gas_for_matching(strategy):
    assert strategy.maxGasForMatching() == 100000
    new_value = Wei("0.05212 ether")
    strategy.setMaxGasForMatching(new_value)
    assert strategy.maxGasForMatching() == new_value
