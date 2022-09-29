from brownie import Contract


def main():
    dai = Contract.from_explorer("0x6b175474e89094c44da98b954eedeac495271d0f")
    balance = dai.balanceOf("0x6b175474e89094c44da98b954eedeac495271d0f")
    print(balance)

    row = "{},0\n".format(balance)

    # Append-adds at last
    dataFile = open("./data/liquidity.csv", "a")  # append mode
    dataFile.write(row)
    dataFile.close()
