# 薅羊毛 Agent

一个基于 Claude 的信用卡薅羊毛助手。管理你手头的信用卡、权益、限时优惠，并给出用卡推荐与新卡评估。

## 功能（期一：地基）

- 数据模型：信用卡、固定权益、限时优惠、消费记录、爬虫数据源。
- REST API：`/api/cards`、`/api/benefits`、`/api/offers`、`/api/transactions`。
- Claude 对话 Agent：`/api/chat`，可通过工具调用读写数据库。
- 简易 Web UI：`/cards`、`/offers`、`/chat`。

## 技术栈

- Python 3.10+ / FastAPI / SQLAlchemy 2
- SQLite（默认，见 `data/yangmao.db`）
- Anthropic SDK（`claude-opus-4-7`）
- Jinja2 模板 + 原生 JS（后续再上 HTMX/React）

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入 ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

打开 http://localhost:8000

## 目录结构

```
app/
  main.py           # FastAPI 入口
  config.py         # 环境变量 & 路径
  db.py             # SQLAlchemy engine + Session
  models.py         # ORM 模型
  schemas.py        # Pydantic 输入输出
  crud.py           # DB 操作
  agent.py          # Claude agent + 工具定义
  routes/           # FastAPI 路由
  templates/        # Jinja2 HTML
```

## 后续计划

- **期二（爬虫）**：`scrapers/` 插件框架，先接入卡惠网、我爱卡。
- **期三（分析）**：新卡评估、月度薅羊毛报告。

## 对话示例

```
你: 我刚办了招行经典白金，年费 3600，首年免年费
Agent: （调用 create_card 并确认）

你: 这张卡有贵宾厅 6 次/年、高尔夫权益
Agent: （调用 create_benefit 两次）

你: 今晚要在盒马吃饭，花大概 300 块，用哪张卡划算？
Agent: （调用 recommend_card 并给建议）
```
