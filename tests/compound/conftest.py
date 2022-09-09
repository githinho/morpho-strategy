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
        # "WBTC",  # WBTC
        # "WETH",  # WETH
        "USDT",  # USDT
        # "DAI",  # DAI
        # "USDC",  # USDC
    ],
    scope="session",
    autouse=True,
)
def token(request):
    yield Contract(token_addresses[request.param])


whale_addresses = {
    "WBTC": "0xbf72da2bd84c5170618fbe5914b0eca9638d5eb5",
    "WETH": "0x28c6c06298d514db089934071355e5743bf21d60",
    "USDT": "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",
    "DAI": "0xf977814e90da44bfa03b6295a0616a897441acec",
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


compound_pool_token_addresses = {
    "WBTC": "0xccF4429DB6322D5C611ee964527D42E5d685DD6a",  # cWBTC
    "WETH": "0x4ddc2d193948926d02f9b1fe9e1daa0718270ed5",  # cETH
    "USDT": "0xf650C3d88D12dB855b8bf7D11Be6C55A4e07dCC9",  # cUSDT
    "DAI": "0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643",  # cDAI
    "USDC": "0x39AA39c021dfbaE8faC545936693aC917d5E7563",  # cUSDC
}


@pytest.fixture(scope="session", autouse=True)
def poolToken(token):
    yield compound_pool_token_addresses[token.symbol()]


@pytest.fixture
def trade_factory():
    yield Contract("0x7BAF843e06095f68F4990Ca50161C2C4E4e01ec6")


@pytest.fixture
def ymechs_safe():
    yield Contract("0x2C01B4AD51a67E2d8F02208F54dF9aC4c0B778B6")


@pytest.fixture
def comp_token():
    token_address = "0xc00e94Cb662C3520282E6f5717214004A7f26888"
    yield Contract(token_address)


@pytest.fixture
def comp_whale(accounts):
    yield accounts.at(
        "0x5608169973d639649196a84ee4085a708bcbf397", force=True
    )  # Compound: Team 3


@pytest.fixture
def weth():
    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    yield Contract(token_address)


@pytest.fixture
def weth_amount(user, weth):
    weth_amount = 10 ** weth.decimals()
    user.transfer(weth, weth_amount)
    yield weth_amount


@pytest.fixture
def vault(pm, gov, rewards, guardian, management, token):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(token, gov, rewards, "", "", guardian, management)
    vault.setDepositLimit(2**256 - 1, {"from": gov})
    vault.setManagement(management, {"from": gov})
    yield vault


@pytest.fixture
def strategy(
    strategist,
    keeper,
    vault,
    poolToken,
    MorphoCompoundStrategy,
    gov,
    trade_factory,
    ymechs_safe,
    token,
):
    strategy = strategist.deploy(
        MorphoCompoundStrategy,
        vault,
        poolToken,
        "StrategyMorphoCompound" + token.symbol(),
    )
    strategy.setKeeper(keeper)
    vault.addStrategy(strategy, 10_000, 0, 2**256 - 1, 1_000, {"from": gov})
    trade_factory.grantRole(
        trade_factory.STRATEGY(),
        strategy.address,
        {"from": ymechs_safe, "gas_price": "0 gwei"},
    )
    strategy.setTradeFactory(trade_factory.address, {"from": gov})
    yield strategy


@pytest.fixture
def uni_address():
    yield "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"


@pytest.fixture
def sushi_address():
    yield "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F"


@pytest.fixture(scope="session")
def RELATIVE_APPROX():
    yield 1e-5


# Function scoped isolation fixture to enable xdist.
# Snapshots the chain before each test and reverts after test completion.
@pytest.fixture(scope="function", autouse=True)
def shared_setup(fn_isolation):
    pass
