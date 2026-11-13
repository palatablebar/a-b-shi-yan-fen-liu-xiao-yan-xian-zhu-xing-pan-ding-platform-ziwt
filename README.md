# abcheck · A/B 实验分流校验与显著性判定台

> 给增长分析组用的「实验记录本」：先查分流比例是否失衡（SRM），再比主指标与守卫指标，
> 最后按固定规则给出 `pass / warn / fail / unreadable`，并留一条可归档的决策记录。

## 1. 真实场景

**委托方**：青柚出行（网约车/租车）· 增长分析组，9 人，每周同时跑 4 个线上实验（首页改版、优惠券、推荐位、新客引导）。

**现状**：产品经理把两组的转化率丢进 Excel，算个差值，差 0.3pp 就宣布「赢了」；
上线后客诉上升才发现守卫指标坏了；分层里挑一个显著的写进汇报，也从没做过多重比较校正。

**三个痛点**

1. 分流比例失衡没人查（SRM）——曝光埋点重复上报、分流器 hash 抖动都看不出来；
2. 只看主指标、忽略守卫指标——结论「显著」但客诉/工单已经变差；
3. 分层随意挑显著、多重比较不校正——6 个分层里总有 1~2 个「p<0.05」，容易被当成真效应。

**上下游**：埋点明细（分桶/曝光/转化/指标值）→ **abcheck 替代「Excel 手算 + 凭感觉判显著」** →
产品评审会决策与实验平台存档（MD/CSV 报告 + 决策记录）。

**角色与权限**

| 角色 | 账号 | 主要页面 | 权限 | 典型动作 |
|---|---|---|---|---|
| admin 增长负责人 | `admin@abcheck.io` | 全部 | 实验/指标/裁决规则维护 + 裁决上线 | 改指标口径、落决策记录 |
| analyst 数据分析师 | `analyst@abcheck.io` | 全部（除裁决写） | 建实验、跑分析、写分层结论 | 触发分析、看分层 BH、导出报告 |
| pm 产品经理 | `pm@abcheck.io` | 全部只读 | 只读结论与报告 | 看判定理由、导出报告给评审会 |

**一天的工作剧本（2026-11-12 上午）**

| 时间 | 动作 | 具体对象 |
|---|---|---|
| 09:12 | 打开实验索引，先看昨天批次的三条结论印章 | `exp_home_feed_1101` 判 unreadable |
| 09:18 | 进「首页信息流改版」详情：曝光口径 52.3% / 47.7%，SRM p≈0.000207 < 0.001 | χ²=13.77, df=1 |
| 09:26 | 给投放同学发批注：变体 B 曝光埋点重复上报，先修埋点再重跑 | 实验备注 |
| 09:41 | 触发「收银台优惠券默认档位」分析：主指标 arpu lift +4.19%、p=0.0311 | run `RUN-EXP_COUPON_DEFAULT_1105-002` |
| 09:47 | 看分层：6 个分层里 2 个原始显著（一线·新客 p=0.0136、一线·老客 p=0.0397），BH 校正后都不显著 | q=0.0814 / 0.1191 |
| 09:52 | 守卫指标：客诉率 p=0.856、工单率 p=0.773，无回归 | 结论 warn |
| 10:05 | 增长负责人落决策「继续观察」，理由写清分层异质与 MDE 边界 | 决策记录 |
| 10:12 | 导出 MD/CSV 报告，附件发产品评审会 | `abcheck-exp_coupon_default_1105-report.md` |

## 2. 主要功能

- **实验台账**：5 个实验 / 11 个变体 / 5 个指标 / 7,400 条分桶曝光，按状态筛选；
- **多臂共同对照**：支持 1 个共同对照 + 多处理方案（如首页文案原版/短文案/领券文案三组流量），
  逐组对账分桶曝光与流量配比（全实验 SRM + 配对 SRM），每个方案独立判定并给可上线状态；
- **分流校验（SRM）**：卡方拟合优度 `χ² = Σ(O−E)²/E`，`p < 0.001` 直接锁定结论 `unreadable`；
- **指标对比**：比例指标两比例 z 检验（合并方差），均值指标 Welch t；输出 `lift / lift_ci95 / p_value / mde_required`；
- **分层下钻 + 多重比较**：城市 × 新老客 6 个分层，分层内 BH FDR 一次、全量（主/守卫/辅助/分层合并）BH 一次；
  多臂时全部方案的检验并入**同一个 BH family**，同一套误报控制下比较所有方案；
- **守卫指标回归**：显著变差（方向按指标定义）→ 该方案结论降级 `fail` / `blocked`；
- **固定规则结论**：`pass / warn / fail / unreadable` 四档 + 可读的理由清单；
  多臂另给 `ship_eligible / watch_only / blocked` 可上线状态，守卫生效或校正后失真的方案不能当赢家；
- **报告与决策**：Markdown 报告 + CSV 明细导出（多臂报告含逐方案对照关系、校正前后 p/q 与可上线状态）；
  决策记录（上线/下线/继续观察）+ 审计留痕。

## 3. 快速启动

```bash
cp .env.example .env
docker compose up -d --build
# 等 5 个服务 healthy（首次构建约 2~4 分钟）
docker compose ps
```

访问：

- 前端（Nginx）：http://localhost:18246
- 后端 API：http://localhost:19246/api/health
- MySQL：`localhost:17746`（库 `abcheck` / 用户 `abcheck`）

seed 在 backend 启动时自动跑一次（`SEED_DEMO=true`），也可手动执行：

```bash
docker compose exec backend python -m scripts.seed_demo
```

幂等：自然键 upsert，重复执行不新增、不覆盖用户修改；结束打印一行
`SEED_SUMMARY brand=abcheck experiments=5 variants=11 metrics=5 assignments=7400 runs=4 users=3`。

**演示账号**（密码统一 `Demo@2026`）

| 角色 | 邮箱 | 说明 |
|---|---|---|
| 增长负责人 admin | `admin@abcheck.io` | 可建实验/改指标/触发分析/裁决 |
| 数据分析师 analyst | `analyst@abcheck.io` | 可建实验/触发分析，不能裁决 |
| 产品经理 pm | `pm@abcheck.io` | 只读；越权调用写接口返回 **403** |

## 4. 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React 18 + TypeScript + Vite + zustand + react-router-dom（自绘 SVG 图表，无图表库/无 CDN） |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.0 + Alembic |
| 异步 | Celery 5 + Redis（分析批次在 worker 中执行） |
| 数据库 | MySQL 8.0 |
| 部署 | Docker Compose：frontend(Nginx) / backend / worker / db / redis，5 个服务均有 healthcheck |
| 统计 | 纯 Python 标准库 `math` 自实现（erf / 不完全 Gamma / 不完全 Beta），无 scipy 依赖，结果逐位可复现 |

## 5. 目录

```
gb-573/
├── backend/
│   ├── src/{config,constants,models,schemas,services,controllers,routes,middlewares,utils}
│   ├── scripts/seed_demo.py          # 幂等 seed（含确定性分桶数据与三臂文案实验）
│   ├── migrations/                   # Alembic（0001 metadata 建表 + 0002 多臂 arms 列）
│   └── entrypoint.sh                 # alembic upgrade head → uvicorn
├── worker/                           # Celery worker + beat 心跳 + 分析任务
├── frontend/src/{api,stores,types,components/{common,business,layout},hooks,pages,router,utils,constants,styles}
├── docker-compose.yml
└── docs/口径与判定规则.md
```

## 6. 环境变量（.env.example）

| 变量 | 默认 | 说明 |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | `abcheck` | 容器名前缀 |
| `FRONTEND_PORT` / `BACKEND_PORT` / `DB_PORT` | 18246 / 19246 / 17746 | 题目分配端口 |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_ROOT_PASSWORD` | abcheck / abcheck / … | MySQL 8.0 |
| `JWT_SECRET` | 演示值 | JWT 签名密钥 |
| `SEED_DEMO` | `true` | 启动时自动 seed |
| `RUNS_PER_MINUTE` | `12` | 每用户每分钟最多触发分析次数（Redis 限流） |
| `MIN_SAMPLE_PER_ARM` | `120` | 每臂样本下限，低于则 unreadable |

## 7. 共享枚举出现位置（前后端各一份）

| 枚举组 | 后端 | 前端 |
|---|---|---|
| 角色 admin/analyst/pm | `backend/src/constants/roles.py` | `frontend/src/constants/roles.ts` |
| 指标 kind/role/direction、实验状态、批次状态、SRM、结论、决策、多臂可上线状态 ship_state | `backend/src/constants/enums.py` | `frontend/src/constants/enums.ts` |

另外：`backend/src/models/*.py` 的字符串列、`frontend/src/types/models.ts` 的联合类型、
`docs/口径与判定规则.md` 与 `README` 的权限表均引用同一套枚举。

## 8. 算法口径（详见 `docs/口径与判定规则.md`）

- SRM：`χ² = Σ(O−E)²/E`，`df=k−1`，`p<0.001` → `unreadable` 且结论锁定；多臂另做逐方案配对 SRM（df=1）；
- 比例指标：`z=(p_t−p_c)/√(p̄(1−p̄)(1/n_c+1/n_t))`，lift CI 用非合并方差标准误；
- 均值指标：Welch t（Welch–Satterthwaite 自由度）；
- `mde_required`：`(z_{1−α/2}+z_{0.8})·SE`，同时给绝对值与相对值；
- 多重比较：Benjamini–Hochberg，`q_i = min_{k≥i}(p_k·m/k)`；多臂时所有方案的全部检验合并一个 family；
- 结论固定规则：SRM/样本不足→unreadable；守卫回归或主指标不显著→fail；
  多臂主指标原始显著但全方案 BH 后失真（q>α）→ fail/blocked；
  分层异质性（≥2 个分层原始显著但 BH 后不显著）/分层反向显著/观测效应低于 MDE→warn；其余 pass。

## 9. 本地开发（不走 Docker）

```bash
# 后端
cd backend && python3.11 -m venv .venv && source .venv/bin/activate
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
export DB_HOST=127.0.0.1 DB_PORT=17746 DB_NAME=abcheck DB_USER=abcheck DB_PASSWORD=abcheck_pw_2026
export REDIS_URL=redis://127.0.0.1:6379/0 SEED_DEMO=true
alembic upgrade head && uvicorn src.main:app --reload --port 8000

# worker（另一个 shell，PYTHONPATH 指向 backend）
PYTHONPATH=.:backend celery -A worker_src.config.celery_app worker -B -l info

# 前端
cd frontend && npm install && npm run dev   # http://localhost:5173，/api 代理到 19246
```

## 10. Docker 说明

- 5 个服务：`frontend`(Nginx 托管 dist) / `backend`(uvicorn) / `worker`(Celery + beat) / `db`(MySQL 8.0) / `redis`(7-alpine)；
- 依赖用 `service_healthy`；命名卷 `db_data`、`redis_data`；
- Nginx：`location /api/ { proxy_pass http://backend:8000/; }` + SPA 回落；
- worker 的 healthcheck 先看 Redis 心跳键（beat 每 20s 写），再兜底 `celery inspect ping`。

## 11. License

内部演示项目，仅用于评审与教学；文中「青柚出行」为虚构客户。
