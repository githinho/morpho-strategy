import pytest
from brownie import config
from brownie import Contract


@pytest.fixture
def gov(accounts):
    yield accounts.at("0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52", force=True)


@pytest.fixture
def user(accounts):
    yield accounts[0]


@pytest.fixture
def rewards(accounts):
    yield accounts[1]


@pytest.fixture
def guardian(accounts):
    yield accounts[2]


@pytest.fixture
def management(accounts):
    yield accounts[3]


@pytest.fixture
def strategist(accounts):
    yield accounts[4]


@pytest.fixture
def keeper(accounts):
    yield accounts[5]


token_addresses = {
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # WBTC
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT
    "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI
    "USDC": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC
}

# TODO: uncomment those tokens you want to test as want
@pytest.fixture(
    params=[
        "WBTC",  # WBTC
        "WETH",  # WETH
        "USDT",  # USDT
        "DAI",  # DAI
        "USDC",  # USDC
    ],
    scope="session",
    autouse=True,
)
def token(request):
    yield Contract(token_addresses[request.param])


whale_addresses = {
    "WBTC": "0xbf72da2bd84c5170618fbe5914b0eca9638d5eb5",
    "WETH": "0x2f0b23f53734252bda2277357e97e1517d6b042a",
    "USDT": "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",
    "DAI": "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7",
    "USDC": "0x0a59649758aa4d66e25f08dd01271e891fe52199",
}


@pytest.fixture(scope="session", autouse=True)
def token_whale(accounts, token):
    yield accounts.at(whale_addresses[token.symbol()], force=True)


token_prices = {
    "WBTC": 35_000,
    "WETH": 2_000,
    "USDT": 1,
    "USDC": 1,
    "DAI": 1,
}


@pytest.fixture(autouse=True)
def amount(token, token_whale, user):
    # this will get the number of tokens (around $1m worth of token)
    amillion = round(1_000_000 / token_prices[token.symbol()])
    amount = amillion * 10 ** token.decimals()
    # # In order to get some funds for the token you are about to use,
    # # it impersonate a whale address
    if amount > token.balanceOf(token_whale):
        amount = token.balanceOf(token_whale)
    token.transfer(user, amount, {"from": token_whale})
    yield amount


aave_pool_token_addresses = {
    "WBTC": "0x9ff58f4fFB29fA2266Ab25e75e2A8b3503311656",  # aWBTC
    "WETH": "0x030bA81f1c18d280636F32af80b9AAd02Cf0854e",  # aWETH
    "USDT": "0x3Ed3B47Dd13EC9a98b44e6204A523E766B225811",  # aUSDT
    "DAI": "0x028171bCA77440897B824Ca71D1c56caC55b68A3",  # aDAI
    "USDC": "0xBcca60bB61934080951369a648Fb03DF4F96263C",  # aUSDC
}


@pytest.fixture(scope="session", autouse=True)
def poolToken(token):
    yield aave_pool_token_addresses[token.symbol()]


@pytest.fixture
def weth():
    yield Contract(token_addresses["WETH"])


@pytest.fixture
def weth_amount(user, weth):
    weth_amount = 10 ** weth.decimals()
    user.transfer(weth, weth_amount)
    yield weth_amount


@pytest.fixture
def usdt():
    yield Contract(token_addresses["USDT"])


@pytest.fixture
def usdt_amount(accounts, usdt, user):
    amount = 10_000 * 10 ** usdt.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate an exchange address to use it's funds.
    reserve = accounts.at(whale_addresses["USDT"], force=True)
    usdt.transfer(user, amount, {"from": reserve})
    yield amount


@pytest.fixture
def vault(pm, gov, rewards, guardian, management, token):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(token, gov, rewards, "", "", guardian, management)
    vault.setDepositLimit(2**256 - 1, {"from": gov})
    vault.setManagement(management, {"from": gov})
    vault.setManagementFee(0, {"from": gov})
    yield vault


@pytest.fixture
def strategy(strategist, keeper, vault, poolToken, token, MorphoAaveStrategy, gov):
    strategy = strategist.deploy(
        MorphoAaveStrategy, vault, poolToken, "StrategyMorphoAave" + token.symbol()
    )
    strategy.setKeeper(keeper)
    vault.addStrategy(strategy, 10_000, 0, 2**256 - 1, 1_000, {"from": gov})
    yield strategy


@pytest.fixture(scope="session")
def RELATIVE_APPROX():
    yield 1e-5


# Function scoped isolation fixture to enable xdist.
# Snapshots the chain before each test and reverts after test completion.
@pytest.fixture(scope="function", autouse=True)
def shared_setup(fn_isolation):
    pass
