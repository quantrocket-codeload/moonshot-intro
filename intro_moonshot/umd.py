# Copyright 2020 QuantRocket LLC - All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from moonshot import Moonshot
from moonshot.commission import PerShareCommission

class UpMinusDown(Moonshot):
    """
    Strategy that buys recent winners and sells recent losers.

    Specifically:

    - rank stocks by their performance over the past MOMENTUM_WINDOW days
    - ignore very recent performance by excluding the last RANKING_PERIOD_GAP
    days from the ranking window (as commonly recommended for UMD)
    - buy the TOP_N_PCT percent of highest performing stocks and short the TOP_N_PCT
    percent of lowest performing stocks
    - rebalance the portfolio according to REBALANCE_INTERVAL
    """

    CODE = "umd"
    MOMENTUM_WINDOW = 252 # rank by twelve-month returns
    RANKING_PERIOD_GAP = 22 # but exclude most recent 1 month performance
    TOP_N_PCT = 50 # Buy/sell the top/bottom 50%
    REBALANCE_INTERVAL = "M" # M = monthly; see https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#offset-aliases

    def prices_to_signals(self, prices):
        """
        This method receives a DataFrame of prices and should return a
        DataFrame of integer signals, where 1=long, -1=short, and 0=cash.
        """
        closes = prices.loc["Close"]

        # Calculate the returns
        returns = closes.shift(self.RANKING_PERIOD_GAP)/closes.shift(self.MOMENTUM_WINDOW) - 1

        # Rank the best and worst
        top_ranks = returns.rank(axis=1, ascending=False, pct=True)
        bottom_ranks = returns.rank(axis=1, ascending=True, pct=True)

        top_n_pct = self.TOP_N_PCT / 100

        # Get long and short signals and convert to 1, 0, -1
        longs = (top_ranks <= top_n_pct)
        shorts = (bottom_ranks <= top_n_pct)

        longs = longs.astype(int)
        shorts = -shorts.astype(int)

        # Combine long and short signals
        signals = longs.where(longs == 1, shorts)

        # Resample using the rebalancing interval.
        # Keep only the last signal of the month, then fill it forward
        signals = signals.resample(self.REBALANCE_INTERVAL).last()
        signals = signals.reindex(closes.index, method="ffill")

        return signals

    def signals_to_target_weights(self, signals, prices):
        """
        This method receives a DataFrame of integer signals (-1, 0, 1) and
        should return a DataFrame indicating how much capital to allocate to
        the signals, expressed as a percentage of the total capital allocated
        to the strategy (for example, -0.25, 0, 0.1 to indicate 25% short,
        cash, 10% long).
        """
        weights = self.allocate_equal_weights(signals)
        return weights

    def target_weights_to_positions(self, weights, prices):
        """
        This method receives a DataFrame of allocations and should return a
        DataFrame of positions. This allows for modeling the delay between
        when the signal occurs and when the position is entered, and can also
        be used to model non-fills.
        """
        # Enter the position in the period/day after the signal
        return weights.shift()

    def positions_to_gross_returns(self, positions, prices):
        """
        This method receives a DataFrame of positions and a DataFrame of
        prices, and should return a DataFrame of percentage returns before
        commissions and slippage.
        """
        # We'll enter on the open, so our return is today's open to
        # tomorrow's open
        opens = prices.loc["Open"]
        # The return is the security's percent change over the period,
        # multiplied by the position.
        gross_returns = opens.pct_change() * positions.shift()
        return gross_returns

class USStockCommission(PerShareCommission):
    BROKER_COMMISSION_PER_SHARE = 0.005

class UpMinusDownDemo(UpMinusDown):

    CODE = "umd-demo"
    DB = "usstock-free-1d"
    UNIVERSES = "usstock-free"
    TOP_N_PCT = 50
    COMMISSION_CLASS = USStockCommission
