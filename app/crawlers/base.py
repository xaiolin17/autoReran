from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import pandas as pd


class BaseCrawler(ABC):
    @abstractmethod
    def fetch_stock_data(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        pass

    @abstractmethod
    def fetch_realtime_data(self, stock_code: str) -> Dict:
        pass

    @abstractmethod
    def fetch_stock_list(self) -> List[Dict]:
        pass
