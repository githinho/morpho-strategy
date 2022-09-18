import brownie
import pytest


def test_harvest_exit(
    chain,
    token,
    vault,
    strategy,
    strategist,
    user,
    gov,
    amount,
    RELATIVE_APPROX,
    comp_token,
    comp_whale,
    trade_factory,
    ymechs_safe,
):
    # Disable trade factory so strategy can swap reward tokens to want tokens using sushiswap as fallback option
    strategy.removeTradeFactoryPermissions({"from": gov})

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
        strategy, 2 * strategy.minRewardToClaimOrSell(), {"from": comp_whale}
    )

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
