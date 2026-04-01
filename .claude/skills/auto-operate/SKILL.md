---
name: auto-operate
description: 全自动操作模式。Claude 直接操控所有能操控的系统和平台，最小化人工介入。
argument-hint: "[可选：指定任务，例如 deploy / github / railway / vercel / database]"
---

# AUTO-OPERATE — 全自动操作引擎

**核心原则：Claude 能操作的，绝不让用户手动。**

## 当用户说 /auto-operate 时

立即说：

> 🤖 全自动模式已开启。我会直接操控所有系统，你只需要在真正需要人工时（如扫码支付、账号密码登录）介入。

---

## Claude 能直接操控的系统

### ✅ 完全自动化（无需用户介入）

**部署平台**
| 操作 | 工具 |
|------|------|
| Vercel 部署 | `vercel --yes --prod` |
| Railway 触发部署 | GraphQL API `serviceInstanceDeploy` |
| Railway 设置环境变量 | GraphQL API `variableCollectionUpsert` |
| Railway 创建域名 | GraphQL API `serviceDomainCreate` |
| Railway 查看日志 | GraphQL API `deploymentLogs` |

**代码 & 版本管理**
| 操作 | 工具 |
|------|------|
| Git commit & push | Bash: `git add/commit/push` |
| 创建 GitHub 仓库 | `gh repo create` |
| 创建 PR | `gh pr create` |
| 读写文件 | Read / Write / Edit |
| 搜索代码 | Grep / Glob |

**浏览器自动化**（Playwright MCP）
| 操作 | 工具 |
|------|------|
| 打开页面 | `browser_navigate` |
| 点击按钮 | `browser_snapshot` + `browser_click` |
| 填写表单 | `browser_fill_form` |
| 截图验证 | `browser_take_screenshot` |
| 监听网络请求 | `browser_network_requests` |

**API 调用**
| 平台 | 方式 |
|------|------|
| Railway GraphQL | curl + RAILWAY_API_TOKEN |
| GitHub REST API | `gh api` |
| Vercel API | vercel CLI |
| 任何 HTTP API | curl / Bash |

---

### ⚠️ 需要用户配合的操作（真正无法绕过的）

| 情况 | 原因 | 我怎么做 |
|------|------|---------|
| 微信/支付宝扫码 | 需要手机 | 截图给你，告诉你扫哪里 |
| 短信验证码 | 需要手机 | 告诉你在哪填，你报码给我 |
| 账号密码（不知道） | 安全原因 | 只问一次，记住后续不再问 |
| Apple ID / Face ID | 系统级 | 告知步骤，你操作一次 |
| 银行 U 盾 | 硬件 | 无法自动化，告知操作步骤 |

---

## 标准操作流程

当收到任务时，按以下顺序自动执行：

```
1. 分析任务 → 拆解步骤
2. 识别每步是否可自动化
3. 可自动化的 → 直接执行，不问
4. 不可自动化的 → 一次性告知用户需要做什么
5. 用户完成人工步骤后 → 继续自动化剩余步骤
6. 完成后 → 验证结果，报告状态
```

---

## 实战示例

### 示例 1：完整部署上线
```
用户：帮我把最新代码部署上线

Claude 自动执行：
1. git add . && git commit -m "..." && git push
2. vercel --yes --prod（前端）
3. Railway GraphQL: serviceInstanceDeploy（后端）
4. 验证 https://backend.railway.app/health
5. 报告：前端 ✅ 后端 ✅ 全部上线
```

### 示例 2：Railway 配置数据库
```
用户：帮我配好数据库连接

Claude 自动执行：
1. 查询 Postgres 服务变量（GraphQL）
2. 设置 DATABASE_URL（GraphQL variableCollectionUpsert）
3. 触发重新部署
4. 等待 SUCCESS 状态
5. 验证 /health 接口
```

### 示例 3：浏览器授权操作
```
用户：帮我授权 Railway 访问 GitHub

Claude 自动执行：
1. browser_navigate → Railway settings
2. browser_snapshot → 找"Connect GitHub"按钮
3. browser_click → 点击
4. 等待跳转 → GitHub OAuth 页面
5. browser_snapshot → 找"Authorize"按钮
6. browser_click → 授权完成
7. 报告：GitHub 授权成功 ✅
```

---

## 配合使用
- `/auto-confirm` → 自动点所有确认
- `/ship` → 完整发布流水线
- `/verify` → 自动验证上线结果
- `/debug` → 自动排查问题（查日志、测接口）
