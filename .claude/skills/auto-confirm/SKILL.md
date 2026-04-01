---
name: auto-confirm
description: 自动确认模式。所有 CLI 确认、浏览器弹窗、平台操作，Claude 直接帮你点确认，无需手动介入。
argument-hint: "[可选：指定场景，例如 railway / vercel / github / browser]"
---

# AUTO-CONFIRM — 自动确认模式

**核心原则：凡是 Claude 能代劳的确认，绝不让用户手动操作。**

## 当用户说 /auto-confirm 时

立即激活以下行为准则，并回复：

> ✅ 自动确认模式已激活。接下来所有操作我会直接执行，不再询问"是否继续"。

---

## 自动确认规则

### 1. CLI 命令确认
遇到需要 `--yes` / `-y` / `--force` 等确认参数的命令，**自动加上**：
```bash
# 以下命令自动加 --yes
vercel --yes --prod
npm install --yes
git push --force-with-lease  # 非破坏性强推用这个
railway up --detach
```

### 2. Playwright 浏览器确认
遇到以下类型弹窗，**直接点确认**：
- "确认" / "Continue" / "Proceed" / "OK" 按钮
- "授权" / "Authorize" / "Allow" 按钮
- "部署" / "Deploy" / "Submit" 按钮
- 进度提示（直接继续，不等用户）

**操作方式**：用 `mcp__playwright__browser_snapshot` 找到按钮 ref，立刻 `mcp__playwright__browser_click`。

### 3. Railway / Vercel / GitHub 操作
这些平台操作**全部自动化**，不等用户确认：

| 平台 | 自动操作 |
|------|---------|
| Railway | 部署触发、环境变量设置、重启服务 |
| Vercel | `vercel --yes --prod` 直接部署 |
| GitHub | `git push`、PR 创建、仓库操作 |
| npm/pip | 包安装直接执行 |

### 4. 唯一需要暂停确认的情况
只有以下**高危不可逆**操作才询问：
- 删除生产数据库 / DROP TABLE
- 删除 GitHub 仓库
- 强制覆盖 main 分支（`git push --force`，非 `--force-with-lease`）
- 扣费操作（付费 API、云服务开通收费功能）

---

## 实战示例

**场景 1：Vercel 重新部署**
```
用户：重新部署前端
Claude：（直接执行，不问）
→ vercel --yes --scope zhouxiaohes-projects --prod
→ 部署完成：https://...
```

**场景 2：Railway 环境变量更新**
```
用户：更新 API Key
Claude：（直接调 GraphQL API，不问）
→ variableCollectionUpsert mutation
→ 触发重新部署
→ 完成
```

**场景 3：浏览器 GitHub 授权**
```
Claude 看到"Authorize Railway"按钮
→ 直接 browser_click，不询问
```

---

## 配合其他 Skill 使用
- `/ship` → 自动确认所有发布步骤
- `/auto-operate` → 配合全自动化操作流程
- 部署相关任何步骤 → 不等确认直接跑
