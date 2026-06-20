# Partner Performance Reporting Pipeline

Automated Python pipeline that turns monthly partner **"datagrid"** exports into a single, interactive performance report — replacing a manual, multi-spreadsheet process.

## Overview

Every month the business receives large Excel exports containing per-merchant earnings. This pipeline:

- **Auto-detects** any new monthly datagrid file dropped into the working folder
- **Computes** residual, turnover, and volume metrics per merchant
- **Compiles** every month into a single tidy time-series dataset
- **Generates** a self-contained interactive HTML report (charts render offline)

## Key Features

- **Incremental & cached** — each month's large spreadsheet is parsed once and cached, so re-runs are fast
- **Rolling comparison window** — automatically compares a recent period against a baseline period and flags risers vs fallers
- **Scales** to 200+ partners across 13+ months
- **Zero-config monthly run** — drop in the new file, run one command

## Tech Stack

`Python` · `pandas` · `openpyxl` · `Chart.js` · `HTML`

## How It Works (high level)

1. Discover input files matching `Datagrid-<Month> <Year>.xlsx`
2. Parse and normalise the earnings columns into per-merchant monthly residuals
3. Append to a compiled time-series dataset, caching already-parsed months
4. Build comparison windows (baseline vs recent) and rank the biggest movers
5. Render an interactive HTML dashboard with charts

---

> **Note:** This is a portfolio summary. The production code and all underlying data are confidential and are not included in this repository.
