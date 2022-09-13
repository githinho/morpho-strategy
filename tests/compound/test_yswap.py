import brownie
from brownie import Contract
from brownie import ZERO_ADDRESS
import pytest


def test_profitable_harvest_using_yswap(
    chain,
    token,
    vault,
    strategy,
    user,
    amount,
    RELATIVE_APPROX,
    comp_token,
    comp_whale,
    trade_factory,
    ymechs_safe,
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    before_pps = vault.pricePerShare()

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # Strategy earned reward tokens
    comp_token.transfer(
        strategy, 2 * strategy.minCompToClaimOrSell(), {"from": comp_whale}
    )

    tx_swap = execute_yswap(
        trade_factory,
        ymechs_safe,
        strategy.address,
        comp_token.address,
        token.address,
        comp_token.balanceOf(strategy),
    )
    assert tx_swap.return_value > 0

    # Harvest 2: Realize profit
    chain.sleep(1)
    strategy.harvest()
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)
    profit = token.balanceOf(vault.address)  # Profits go to vault
    assert strategy.estimatedTotalAssets() + profit > amount
    assert vault.pricePerShare() > before_pps


def test_disabling_trade_factory(strategy, comp_token, gov, trade_factory):
    assert strategy.tradeFactory() == trade_factory.address
    strategy.removeTradeFactoryPermissions({"from": gov})
    assert strategy.tradeFactory() == ZERO_ADDRESS
    assert comp_token.allowance(strategy.address, trade_factory.address) == 0


def test_profitable_harvest_exit_using_yswap(
    chain,
    token,
    vault,
    strategy,
    strategist,
    user,
    amount,
    RELATIVE_APPROX,
    comp_token,
    comp_whale,
    trade_factory,
    ymechs_safe,
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    before_pps = vault.pricePerShare()

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # Strategy earned reward tokens
    comp_token.transfer(
        strategy, 2 * strategy.minCompToClaimOrSell(), {"from": comp_whale}
    )

    tx_swap = execute_yswap(
        trade_factory,
        ymechs_safe,
        strategy.address,
        comp_token.address,
        token.address,
        comp_token.balanceOf(strategy),
    )
    assert tx_swap.return_value > 0

    # Harvest 2: Realize profit
    chain.sleep(1)
    strategy.harvest()
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)
    profit = token.balanceOf(vault.address)  # Profits go to vault
    assert strategy.estimatedTotalAssets() + profit > amount
    assert vault.pricePerShare() > before_pps

    ## Set emergency - return all founds to vault
    strategy.setEmergencyExit({"from": strategist})
    strategy.harvest()  ## Remove funds from strategy

    assert strategy.estimatedTotalAssets() == 0
    assert token.balanceOf(strategy) == 0
    assert token.balanceOf(vault) + profit > amount
    assert vault.pricePerShare() > before_pps


def execute_yswap(
    trade_factory,
    ymechs_safe,
    strategy_address,
    token_in_address,
    token_out_address,
    amount_in,
):
    asyncTradeExecutionDetails = [
        strategy_address,
        token_in_address,
        token_out_address,
        amount_in,
        1,
    ]

    # TODO: encode path
    # path = [token_in.address, weth.address, token_out.address]
    # Code in Solidity used to generate path_in_bytes:
    # address[] memory path = new address[](3);
    # path[0] = 0xc00e94Cb662C3520282E6f5717214004A7f26888;
    # path[1] = 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2;
    # path[2] = token.address;
    # return abi.encode(path);
    path_in_bytes = (
        "0x00000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000003000000000000000000000000c00e94cb662c3520282e6f5717214004a7f26888000000000000000000000000c02aaa39b223fe8d0a0e5c4f27ead9083c756cc2000000000000000000000000"
        + token_out_address[2:]
    )

    # Trigger ySwap
    # trade_factory.execute(
    #     AsyncTradeExecutionDetails calldata _tradeExecutionDetails,
    #     address _swapper,
    #     bytes calldata _data
    # ) external returns (uint256 _receivedAmount);
    tx_swap = trade_factory.execute["tuple,address,bytes"](
        asyncTradeExecutionDetails,
        "0x408Ec47533aEF482DC8fA568c36EC0De00593f44",
        path_in_bytes,
        {"from": ymechs_safe},
    )
    return tx_swap
