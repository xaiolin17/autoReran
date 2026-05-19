from typing import List

import pandas as pd


class DataProcessor:
    """
    股票数据处理工具类

    职责:
        提供股票数据的合并、聚合、清洗、重采样等通用数据处理能力。
        所有方法均为静态方法，无需实例化即可调用。

    被调用方:
        - StockService: 在数据获取后调用merge_data/average_data合并多源数据
        - IndicatorService: 在计算指标前调用clean_data清洗数据
        - 其他服务层: 调用resample_data进行周期转换
    """

    @staticmethod
    def merge_data(data_list: List[pd.DataFrame]) -> pd.DataFrame:
        """
        合并多个DataFrame为一个

        参数:
            data_list: DataFrame列表

        返回值:
            pd.DataFrame: 合并后的DataFrame，输入为空则返回空DataFrame

        调用关系:
            被调用: StockService等上层服务合并多源数据
            调用: pd.concat

        关键逻辑:
            1. 检查输入列表是否为空
            2. 使用pd.concat按行合并所有DataFrame
            3. 重置索引后返回
        """
        if not data_list:
            return pd.DataFrame()

        merged = pd.concat(data_list, ignore_index=True)
        return merged

    @staticmethod
    def average_data(data_list: List[pd.DataFrame], method: str = "mean") -> pd.DataFrame:
        """
        对多个DataFrame按分组进行聚合计算

        参数:
            data_list: DataFrame列表
            method: 聚合方法，"mean"表示均值，"median"表示中位数，默认"mean"

        返回值:
            pd.DataFrame: 聚合后的DataFrame，输入为空则返回空DataFrame

        调用关系:
            被调用: StockService等上层服务聚合多源数据
            调用: pd.concat, groupby, agg

        关键逻辑:
            1. 检查输入列表是否为空或仅有一个元素
            2. 合并所有DataFrame
            3. 按datetime+stock_code+period分组
            4. 对数值列使用指定聚合方法（mean/median）
            5. stock_name取第一个，source合并为去重字符串
            6. 返回聚合结果
        """
        if not data_list:
            return pd.DataFrame()

        if len(data_list) == 1:
            return data_list[0]

        merged = pd.concat(data_list, ignore_index=True)

        if merged.empty:
            return pd.DataFrame()

        numeric_cols = [
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
            "amount",
        ]
        group_cols = ["datetime", "stock_code", "period"]

        available_numeric = [col for col in numeric_cols if col in merged.columns]
        available_group = [col for col in group_cols if col in merged.columns]

        if not available_group or not available_numeric:
            return merged

        agg_dict = {}
        for col in available_numeric:
            if method == "mean":
                agg_dict[col] = "mean"
            elif method == "median":
                agg_dict[col] = "median"
            else:
                agg_dict[col] = "mean"

        if "stock_name" in merged.columns:
            agg_dict["stock_name"] = "first"
        if "source" in merged.columns:
            agg_dict["source"] = lambda x: ",".join(set(x))

        result = merged.groupby(available_group, as_index=False).agg(agg_dict)
        return result

    @staticmethod
    def clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗股票数据，去除无效和异常记录

        参数:
            df: 原始股票数据DataFrame

        返回值:
            pd.DataFrame: 清洗后的DataFrame，按时间排序

        调用关系:
            被调用: IndicatorService.calculate_indicators_for_df_static 等计算指标前调用
            调用: DataFrame.dropna, drop_duplicates, sort_values

        关键逻辑:
            1. 去除包含NaN的价格记录
            2. 过滤成交量为负的记录
            3. 验证价格逻辑：high >= low, high >= open, high >= close, low <= open, low <= close
            4. 按stock_code+period+datetime去重，保留第一条
            5. 按时间正序排序并重置索引
        """
        if df.empty:
            return df

        required_cols = [
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "volume",
        ]
        available_cols = [col for col in required_cols if col in df.columns]

        if len(available_cols) < len(required_cols):
            df = df.dropna(subset=available_cols)
        else:
            df = df.dropna(subset=required_cols)

        df = df[df["volume"] >= 0]
        df = df[df["high_price"] >= df["low_price"]]
        df = df[df["high_price"] >= df["open_price"]]
        df = df[df["high_price"] >= df["close_price"]]
        df = df[df["low_price"] <= df["open_price"]]
        df = df[df["low_price"] <= df["close_price"]]

        # 去除重复数据：按 stock_code + period + datetime 去重，保留第一条
        dup_cols = ["stock_code", "period", "datetime"]
        dup_cols_available = [col for col in dup_cols if col in df.columns]
        if len(dup_cols_available) >= 2:
            before_dedup = len(df)
            df = df.drop_duplicates(subset=dup_cols_available, keep="first")
            after_dedup = len(df)
            if before_dedup != after_dedup:
                print("[DataProcessor] 去重: 从 " + str(before_dedup) + " 条减少到 " + str(after_dedup) + " 条")

        # 修正日期：将所有非交易日的数据日期修正为向前最近的交易日
        if "datetime" in df.columns:
            from app.services.indicator_service import _fix_trading_date

            original_dates = df["datetime"].copy()
            df["datetime"] = df["datetime"].apply(lambda x: _fix_trading_date(x) if pd.notna(x) else x)
            # 记录修正的日期
            for i in range(len(df)):
                orig = original_dates.iloc[i]
                fixed = df["datetime"].iloc[i]
                if pd.notna(orig) and pd.notna(fixed) and orig.date() != fixed.date():
                    print(
                        "[DataProcessor] 日期修正: "
                        + str(orig.date())
                        + " -> "
                        + str(fixed.date())
                        + " (非交易日修正为最近交易日)"
                    )

        # 按日期去重：同一天保留时间较晚的数据（16:00:00 优先于 00:00:00）
        if "datetime" in df.columns and not df.empty:
            # 提取日期部分用于分组
            df["_date"] = df["datetime"].dt.date

            before_dedup = len(df)
            # 按 stock_code + period + 日期分组，保留 datetime 最大的记录（时间较晚的）
            df = df.sort_values("datetime").groupby(["stock_code", "period", "_date"], as_index=False).last()
            after_dedup = len(df)

            # 删除临时列
            df = df.drop(columns=["_date"])

            if before_dedup != after_dedup:
                print("[DataProcessor] 按日期去重: 从 " + str(before_dedup) + " 条减少到 " + str(after_dedup) + " 条")

        df = df.sort_values("datetime").reset_index(drop=True)
        return df

    @staticmethod
    def resample_data(df: pd.DataFrame, target_period: str) -> pd.DataFrame:
        """
        将数据重采样到指定周期

        参数:
            df: 原始股票数据DataFrame，必须包含datetime列
            target_period: 目标周期（1m/5m/15m/30m/1h/1d/1w/1M）

        返回值:
            pd.DataFrame: 重采样后的DataFrame

        调用关系:
            被调用: 上层服务需要进行周期转换时
            调用: DataFrame.resample, agg

        关键逻辑:
            1. 将datetime列设为索引
            2. 将目标周期映射为pandas频率字符串
            3. 按目标频率重采样
            4. open取first，high取max，low取min，close取last
            5. volume和amount取sum
            6. 补充stock_code、stock_name、period、source字段
            7. 重置索引返回
        """
        if df.empty:
            return df

        df = df.set_index("datetime").sort_index()

        period_map = {
            "1m": "1T",
            "5m": "5T",
            "15m": "15T",
            "30m": "30T",
            "1h": "1H",
            "1d": "1D",
            "1w": "1W",
            "1M": "1M",
        }

        freq = period_map.get(target_period, "1D")

        resampled = (
            df.resample(freq)
            .agg(
                {
                    "open_price": "first",
                    "high_price": "max",
                    "low_price": "min",
                    "close_price": "last",
                    "volume": "sum",
                    "amount": "sum",
                }
            )
            .dropna()
        )

        resampled["stock_code"] = df["stock_code"].iloc[0] if "stock_code" in df.columns else None
        resampled["stock_name"] = df["stock_name"].iloc[0] if "stock_name" in df.columns else None
        resampled["period"] = target_period
        resampled["source"] = "resampled"

        resampled = resampled.reset_index()
        return resampled

    @staticmethod
    def generate_sample_data(
        stock_code: str,
        period: str = "1d",
        days: int = 365,
        base_price: float = 100.0,
    ) -> pd.DataFrame:
        """
        生成模拟数据（已禁用）

        参数:
            stock_code: 股票代码
            period: 时间周期
            days: 生成天数
            base_price: 基础价格

        返回值:
            无（始终抛出异常）

        调用关系:
            被调用: 不再被调用（已禁用）
            调用: 无

        关键逻辑:
            直接抛出RuntimeError，禁止使用模拟数据，强制使用真实数据源
        """
        raise RuntimeError("模拟数据已禁用，请确保 TickFlow 可用或从数据库加载数据。" "股票代码: " + stock_code)
