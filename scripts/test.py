import os
from brownie import Contract
from brownie import chain


def main():
    strategyAddress = getEnvVariable("STRATEGY_ADDRESS")
    dai = Contract.from_explorer(strategyAddress)
    balance = dai.balanceOf(strategyAddress)
    timestamp = chain.time()
    row = "{},{},0,0,0,0,0,0,99\n".format(timestamp, balance)

    os.chdir("data/")
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
        dataFile.write("Timestamp,Strategy Total Balance,Strategy Balance in P2P,Strategy Balance On Pool,Market P2P Supply,Market P2P Borrow,Market Pool Supply,Market Pool Borrow,Max P2P Supply\n")
        dataFile.write(row)
        dataFile.close()

def getEnvVariable(key):
    try:
        return os.environ[key]
    except KeyError:
        print("ERROR: Please set the environment variable:", key)
        exit(1)
