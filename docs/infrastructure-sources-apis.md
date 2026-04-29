# `backend/infrastructure/sources/` API 清单

本文档梳理 `backend/infrastructure/sources/` 目录下所有的外部数据访问，包括 URL、目的、返回结果 schema，以及该接口在 source 层的缓存策略。

> 调用方式说明
> - `eastmoney_hk.py` 中的 `fetch_hk_f10_main_indicator_paginated` 通过 `requests.get` 直连东方财富 F10 后端。
> - 其余调用统一通过 [AKShare](https://akshare.akfamily.xyz/) 转发上游 HTTP 接口；标注的 URL 为底层数据源。
> - 走 AKShare 的调用统一封装在 `ak_call_with_retry`（`backend/infrastructure/akshare_client.py`），失败会按策略重试。

> 缓存策略说明
> - 所有外部 API 调用都在 source 层做了磁盘缓存（`backend/infrastructure/disk_cache.py`），上层 repository / application 不再做重复缓存。
> - 缓存工具：`cached_call`（封装 `ak_call_with_retry` + 缓存读写）、`cache_get` / `cache_set`（手写包装时使用）。
> - TTL 常量：
>   - `TTL_STOCK_INFO = 10 分钟`
>   - `TTL_FINANCIAL = 1 天`
>   - `TTL_PRICE = 1 天`
> - “缓存层”一列标识缓存包装的位置：
>   - **函数级**：在该函数入口检查缓存，函数返回前写入缓存。
>   - **聚合层**：函数本身聚合多个底层 AKShare 调用，缓存的是合并后的最终结果。

---

## 1. `eastmoney_hk.py` —— 港股（东方财富 F10）

### 1.1 `fetch_hk_f10_main_indicator_paginated`（直连 HTTP）

- **调用方式**：`requests.get(url, params=...)`
- **URL**：`https://datacenter.eastmoney.com/securities/api/data/v1/get`
- **关键 Query 参数**：
  - `reportName=RPT_HKF10_FN_MAININDICATOR`
  - `columns=HKF10_FN_MAININDICATOR`
  - `pageNumber`、`pageSize=200`
  - `sortColumns=STD_REPORT_DATE`、`sortTypes=-1`
  - `filter=(SECUCODE="00700.HK")`，年度模式追加 `(DATE_TYPE_CODE="001")`
- **目的**：分页抓取港股 F10 主要财务指标（按报告期或年度）。
- **缓存**：函数级，key=`hk_f10_main_indicator:{hk_code}:{indicator_mode}`，TTL=`TTL_FINANCIAL`（缓存的是分页合并后的整张 DataFrame）。
- **返回 JSON 结构（节选）**：

```json
{
  "result": {
    "data": [
      {
        "SECUCODE": "00700.HK",
        "REPORT_DATE": "2024-12-31",
        "STD_REPORT_DATE": "2024-12-31",
        "OPERATE_INCOME": 660257.00,
        "OPERATE_INCOME_YOY": 8.40,
        "HOLDER_PROFIT": 194073.00,
        "HOLDER_PROFIT_YOY": 68.42,
        "BASIC_EPS": 20.81,
        "GROSS_PROFIT_RATIO": 52.55,
        "NET_PROFIT_RATIO": 29.39,
        "ROE_AVG": 21.30,
        "ROA": 12.10,
        "DEBT_ASSET_RATIO": 47.30,
        "CURRENT_RATIO": 1.32
      }
    ]
  }
}
```

代码取 `result.data` 转 DataFrame，再交由 `normalize_hk_indicator_df` 处理嵌套字典列。

### 1.2 经 AKShare 转发的港股接口

| 函数 | AKShare 接口 | 上游来源 | 目的 | 返回 schema（关键列） | 缓存层 / TTL |
|---|---|---|---|---|---|
| `hk_latest_shares_and_mcap` | `ak.stock_hk_financial_indicator_em` | 东方财富 `emweb.eastmoney.com/PC_HKF10/CoreIndex/...` | 取港股最新核心指标（已发行股本、总市值） | DataFrame：`已发行股本(股)`、`总市值(港元)`、`港股市值(港元)` 等 | 函数级（`cached_call`），key=`hk_core_indicator:{hk_code}` / `TTL_STOCK_INFO` |
| `fetch_stock_info_hk`（聚合） | `ak.stock_hk_security_profile_em` | 东方财富 F10 证券资料 | 证券简称 | DataFrame：`证券简称` 等 | 聚合层缓存最终 dict，key=`stock_info_hk:{hk_code}` / `TTL_STOCK_INFO` |
| 同上 | `ak.stock_hk_company_profile_em` | 东方财富 F10 公司资料 | 行业 | DataFrame：`所属行业` 等 | 同上 |
| 同上（兜底） | `ak.stock_hk_hist` | 东方财富港股历史行情 | 取最新收盘价兜底现价 | DataFrame：`日期`、`开盘`、`收盘`、`最高`、`最低`、`成交量`、`成交额` | 同上 |
| `fetch_cash_flow_hk` | `ak.stock_financial_hk_report_em`（`symbol="现金流量表"`, `indicator="报告期"`） | 东方财富港股现金流量表 | 港股 OCF / CAPEX（YTD 累计值，留待下游去累计） | DataFrame：`SECUCODE`、`REPORT_DATE`、`STD_ITEM_CODE`（`003999`=经营现金流净额、`005007`=资本支出）、`AMOUNT` | 函数级（`cache_get`/`cache_set`），key=`cash_flow_hk:{hk_code}:{window_years}` / `TTL_FINANCIAL` |
| `fetch_dividend_history_hk` | `ak.stock_hk_dividend_payout_em` | 东方财富港股分红派息 | 港股分红历史 | DataFrame：`公告日期`、`除净日`、`分红方案`、`派息金额` 等 | 函数级（`cached_call`），key=`dividend_history_hk:{hk_code}` / `TTL_FINANCIAL` |
| `fetch_price_history_hk` | `ak.stock_hk_hist`（`adjust="qfq"`） | 东方财富港股历史行情 | 月线 / 日线行情（前复权） | 同上 `stock_hk_hist` | 函数级（`cached_call`），key=`price_history:{period}:HK:{hk_code}:{start}:{end}` / `TTL_PRICE` |

---

## 2. `baidu_hk.py` —— 港股总市值历史（百度股市通，直连 HTTP）

- **调用方式**：`requests.get(url, params=...)`（绕过 AKShare 包装，原因详见模块 docstring：akshare 1.18.55 的 `stock_hk_valuation_baidu` 不跟随 302 跳转，导致 JSON 解析失败）
- **URL**：`https://gushitong.baidu.com/opendata`
- **关键 Query 参数**：
  - `resource_id=51171`、`market=hk`、`finClientType=pc`
  - `code=00700`（5 位港股代码）
  - `query`/`tag`：`总市值`（也支持 PE / PB / PS / PCF 等）
  - `chart_select=全部`（也支持 `近一年` / `近三年`，仅这两档为日度，`全部` 为约双周一条）
- **目的**：取港股历史总市值（亿港元，点位时序值），作为 `load_hk_market_cap_frame` 的唯一数据源。
- **覆盖范围**：`period="全部"` 可回溯到上市日（如 00700 自 2004-06-20，约 22 年），频率约双周一条。
- **缓存**：函数级（`cache_get`/`cache_set`），key=`hk_valuation_baidu:{hk_code}:{indicator}:{period}` / `TTL_PRICE`。
- **返回 JSON 路径（节选）**：

```text
Result[0].DisplayData.resultData.tplData.result.chartInfo[0].body
→ [["2024-12-31", 38500.12], ["2024-12-15", 38120.47], ...]
```

代码读取 `body` 后转 DataFrame，`indicator="总市值"` 时第二列重命名为 `market_cap`（亿港元），其它指标列名为 `value`。

---

## 3. `eastmoney_a.py` —— A 股（东方财富 K 线 + 估值分析）

| 函数 | AKShare 接口 | 上游 | 目的 | 返回 schema | 缓存层 / TTL |
|---|---|---|---|---|---|
| `fetch_price_history_a` | `ak.stock_zh_a_hist`（`adjust="qfq"`） | 东方财富 A 股历史行情 | A 股月 / 日线（前复权） | DataFrame：`日期`、`开盘`、`收盘`、`最高`、`最低`、`成交量`、`成交额`、`振幅`、`涨跌幅`、`涨跌额`、`换手率` | 函数级（`cached_call`），key=`price_history:{period}:A:{code}:{start}:{end}` / `TTL_PRICE` |
| `fetch_value_em_history` | `ak.stock_value_em` | 东方财富 [估值分析](https://emweb.securities.eastmoney.com/PC_HSF10/ValueAnalysis/Index?code=) | A 股每日总市值（及 PE/PB/PS/PCF 等估值列） | DataFrame：`数据日期`、`总市值`（元，已转为亿元）、`流通市值`、`总股本`、`流通股本`、`PE-TTM`、`市净率`、`PEG`、`市现率`、`市销率` 等 | 函数级（`cached_call`），key=`stock_value_em:{code}` / `TTL_PRICE` |
| `load_a_market_cap_frame` | 委托 `fetch_value_em_history` | 同上 | A 股月度市值 frame（应用 `restrict_and_resample_mcap`） | DataFrame：`date`、`market_cap`（亿元） | 自身不缓存，仅复用底层 `stock_value_em` 缓存 |

> 覆盖范围：`stock_value_em` 多数 A 股自 2018 起；老股票超出窗口的部分会返回空帧，下游（`MarketCapHistory`）按空处理。

---

## 4. `ths_a_share.py` —— A 股（同花顺）

| 函数 | AKShare 接口 | 上游 | 目的 | 返回 schema | 缓存层 / TTL |
|---|---|---|---|---|---|
| `fetch_financial_abstract` | `ak.stock_financial_abstract_ths`（`indicator="按报告期"`） | 同花顺 F10 财务摘要 | 季度财务摘要（营收、净利、EPS、ROE 等） | DataFrame：`报告期`、`净利润`、`营业总收入`、`营业利润`、`归属于母公司股东的净利润`、`扣除非经常性损益后的净利润`、`基本每股收益`、`每股净资产`、`净资产收益率`、`销售毛利率` 等 | 函数级（`cached_call`），key=`financial_abstract:{code}:{window_years}` / `TTL_FINANCIAL` |
| `fetch_financial_indicator` | `ak.stock_financial_analysis_indicator` | 新浪财经财务分析指标 | 完整财务分析指标（含资产负债率、流动比率等） | DataFrame：`日期`、`摊薄每股收益(元)`、`加权净资产收益率(%)`、`总资产报酬率(%)`、`资产负债率(%)`、`流动比率`、`速动比率`、`现金比率(%)`、`主营业务利润率(%)` 等数十列 | 函数级（`cached_call`），key=`financial_indicator:{code}:{start_year}` / `TTL_FINANCIAL` |
| `fetch_cash_flow` | `ak.stock_financial_cash_ths`（`indicator="按报告期"`） | 同花顺 F10 现金流量表 | A 股季度现金流量表 | DataFrame：`报告期`、`经营活动产生的现金流量净额`、`投资活动产生的现金流量净额`、`筹资活动产生的现金流量净额`、`购建固定资产、无形资产和其他长期资产支付的现金` 等 | 函数级（`cached_call`），key=`cash_flow:{code}:{window_years}` / `TTL_FINANCIAL` |
| `fetch_dividend_history` | `ak.stock_history_dividend_detail`（`indicator="分红"`） | 新浪财经分红配股 | A 股分红实施记录 | DataFrame：`公告日期`、`送股(股)`、`转增(股)`、`派息(税前)(元)`、`进度`（`实施` / `不分配`）、`除权除息日`、`股权登记日` 等 | 函数级（`cached_call`），key=`dividend_history:{code}` / `TTL_FINANCIAL` |

---

## 5. `xueqiu.py` —— A 股（雪球资料 + 行情）

| 函数 | AKShare 接口 | 上游 URL | 目的 | 返回 schema | 缓存层 / TTL |
|---|---|---|---|---|---|
| `fetch_stock_info_a`（聚合） | `ak.stock_individual_basic_info_xq` | `https://stock.xueqiu.com/v5/stock/f10/cn/company.json` | 公司基本信息（简称、行业等） | DataFrame：两列 `item`、`value`；关键 key：`org_short_name_cn`、`affiliate_industry`（dict, `ind_name`）、`pre_name_cn`、`org_cn_introduction` 等 | 聚合层缓存最终 dict，key=`stock_info_xq:{code}` / `TTL_STOCK_INFO` |
| 同上 | `ak.stock_individual_spot_xq` | `https://stock.xueqiu.com/v5/stock/quote.json` | 实时行情（现价、总市值、总股本） | DataFrame：两列 `item`、`value`；关键 key：`现价`、`资产净值/总市值`、`基金份额/总股本`、`涨跌`、`涨幅`、`成交量`、`成交额` 等 | 同上 |

调用结果合并为 `dict` 后，统一暴露 `最新` / `总市值` / `总股本` / `行业` / `股票简称` 等键，与东方财富版兼容。

---

## 6. `stock_lists.py` —— 全市场代码-名称清单

| 函数 | AKShare 接口 | 上游 | 目的 | 返回 schema | 缓存层 / TTL |
|---|---|---|---|---|---|
| `fetch_a_share_code_name_df`（聚合，主） | `ak.stock_info_a_code_name` | 东方财富 A 股清单 | 全 A 股代码-名称 | DataFrame：`code`、`name`（归一化后） | 聚合层缓存最终 DataFrame，key=`a_share_code_name_list` / `TTL_FINANCIAL` |
| 同上（兜底 1） | `ak.stock_info_sh_name_code(indicator="A股")` | 上交所官网 | 沪市 A 股 | 原始 `证券代码`/`证券简称` 或 `A股代码`/`A股简称`，归一为 `code`、`name` | 同上 |
| 同上（兜底 2） | `ak.stock_info_sz_name_code(indicator="A股")` | 深交所官网 | 深市 A 股 | 同上 | 同上 |
| `fetch_hk_stock_list_df`（聚合） | `ak.stock_hk_spot_em` | 东方财富港股全量行情 | 港股全清单 | 含 `代码`、`名称`（或 `中文名称`）等行情列；归一为 `code`（5 位 zfill）、`name` | 聚合层缓存最终 DataFrame，key=`hk_stock_list` / `TTL_FINANCIAL` |
| 同上（兜底 1） | `ak.stock_hk_main_board_spot_em` | 东方财富港股主板 | 港股主板 | 同上 | 同上 |
| 同上（兜底 2） | `ak.stock_hk_spot` | 新浪港股 | 港股全清单 | 同上 | 同上 |

> `load_hk_list_from_sources` 是 `fetch_hk_stock_list_df` 的内部辅助函数，不单独缓存；缓存边界落在 `fetch_hk_stock_list_df`。

---

## 7. `_mcap_base.py` 与 `__init__.py`

不直接发起任何外部 API 请求：

- `_mcap_base.py`：纯工具函数 `restrict_and_resample_mcap`（窗口截断 + 月末重采样）、`monthly_mcap_rows`、`quarterly_mcap_rows`。无类、无 fallback 链 —— 上游失败时直接返回空 DataFrame，由 repository 层映射为空 `MarketCapHistory`。
- `__init__.py`：`load_market_cap_frame(mkt, code, window_years, period)` 工厂，按市场分别委托 `load_hk_market_cap_frame`（→ §2 baidu）和 `load_a_market_cap_frame`（→ §3 eastmoney 估值分析）。

---

## 8. 缓存与重试一览

- **磁盘缓存**（`backend/infrastructure/disk_cache.py`）
  - `TTL_STOCK_INFO = 10 分钟`：港股 / A 股个股资料、港股核心指标
  - `TTL_FINANCIAL = 1 天`：财报、现金流、分红历史、股本变动、股票清单
  - `TTL_PRICE = 1 天`：行情历史（K 线）
- **缓存边界**：所有外部 API 调用都在 source 层做了缓存（函数级或聚合层），上层 `repositories/` 与 `application/` 不再做重复缓存。
- **重试**：所有走 AKShare 的调用通过 `ak_call_with_retry`（`backend/infrastructure/akshare_client.py`）统一包装；`cached_call` 内部已经默认走该重试封装，对于使用 `cache_get`/`cache_set` 手写包装的接口，仍直接用 `ak_call_with_retry` 调用底层 AKShare 函数。
