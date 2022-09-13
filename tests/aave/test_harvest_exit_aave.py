import brownie
import pytest


def test_harvest_exit(
    chain,
    token,
    vault,
    strategy,
    strategist,
    user,
    amount,
    RELATIVE_APPROX,
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

    # # increase lending interest
    chain.sleep(100 * 24 * 3600)
    chain.mine(1)

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
