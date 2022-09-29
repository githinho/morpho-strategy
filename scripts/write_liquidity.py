import os
from brownie import Contract
from brownie import chain


def main():
    os.chdir("data/")
    addresses = getEnvVariable("STRATEGY_ADDRESSES")
    for address in addresses.split(","):
        fetchAndStoreLiquidityForStrategy(address.strip())


def getEnvVariable(key):
    try:
        return os.environ[key]
    except KeyError:
        print("ERROR: Please set the environment variable:", key)
        exit(1)


def fetchAndStoreLiquidityForStrategy(strategyAddress):
    # it would be nice to remove Contract.from_explorer and import MorphoStrategy class but brownie cannot import abstract class
    strategy = Contract.from_explorer(strategyAddress)
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

    fileName = "strategy_" + strategyAddress + ".csv"
    print("Writing liquidity data to file:", fileName)
    if os.path.isfile(fileName):
        # append existing file
        dataFile = open(fileName, "a")
        dataFile.write(row)
        dataFile.close()
    else:
        # create file
        dataFile = open(fileName, "w+")
        # add table header
        dataFile.write(
            "Timestamp,Strategy Total Balance,Strategy Balance in P2P,Strategy Balance"
            " On Pool,Market P2P Supply,Market P2P Borrow,Market Pool Supply,Market"
            " Pool Borrow,Max P2P Supply\n"
        )
        dataFile.write(row)
        dataFile.close()
