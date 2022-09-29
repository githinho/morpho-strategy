from brownie import Contract


def main():
    # TODO: set strategy contract address
    strategy_address = "0x"
    # it would be nice to remove Contract.from_explorer and import MorphoStrategy class but brownie cannot import abstract class
    strategy = Contract.from_explorer(strategy_address)
    timestamp = chain.time()  # or use chain.height for block number
    (
        strategyBalanceOnPool,
        strategyBalanceInP2P,
        strategyTotalBalance,
    ) = strategy.getStrategySupplyBalance()
    (
        p2pSupplyAmount,
        p2pBorrowAmount,
        poolSupplyAmount,
        poolBorrowAmount,
    ) = strategy.getCurrentMarketLiquidity()
    maxP2PSupply = strategy.getMaxP2PSupply()

    # create row in CSV table
    row = "{},{},{},{},{},{},{},{},{}\n".format(
        timestamp,
        strategyTotalBalance,
        strategyBalanceInP2P,
        strategyBalanceOnPool,
        p2pSupplyAmount,
        p2pBorrowAmount,
        poolSupplyAmount,
        poolBorrowAmount,
        maxP2PSupply,
    )

    # append mode
    dataFile = open("./data/liquidity.csv", "a")
    dataFile.write(row)
    dataFile.close()
