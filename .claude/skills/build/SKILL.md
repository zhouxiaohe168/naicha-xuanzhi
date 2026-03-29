---
name: build
description: 快速搭建新项目。当用户想要开始一个新的产品/工具/网站时使用，帮助从零搭建项目骨架。
argument-hint: "[项目类型，例如：落地页、API服务、Chrome插件、SaaS]"
---

# BUILD — 一人公司快速建造器

帮助用户从零开始搭建项目，选择最简单、最适合一人公司的技术方案。

## 核心原则

1. **能用模板就不从零写** — 速度第一
2. **能用一个框架就不用两个** — 简单第一
3. **能免费就不花钱** — 成本第一
4. **能部署就不只在本地跑** — 结果第一

## 当用户说 /build 时

### Step 1: 确认需求
快速问用户：
- 你要做什么？（一句话描述）
- 给谁用？（自己 / 朋友 / 公开产品）
- 要不要赚钱？（免费工具 / 付费产品）

### Step 2: 推荐技术方案

根据项目类型推荐最简方案：

| 项目类型 | 推荐方案 | 部署 |
|----------|----------|------|
| **落地页/展示站** | HTML + Tailwind（单文件） | GitHub Pages / Vercel |
| **全栈Web应用** | Next.js / Replit | Vercel / Replit |
| **API服务** | Python + FastAPI | Railway / Render |
| **Chrome插件** | HTML + JS（Manifest V3） | Chrome Web Store |
| **CLI工具** | Python + Click | PyPI |
| **移动应用** | React Native / PWA | App Store / Web |
| **AI应用** | Python + Claude API + Streamlit | Streamlit Cloud |
| **数据仪表盘** | Python + Streamlit / Gradio | Streamlit Cloud |
| **自动化Bot** | Python + 定时任务 | Railway / Cron |

### Step 3: 生成项目骨架
直接用代码创建项目基础结构：
- 初始化项目目录
- 创建核心文件
- 配置依赖
- 写好 README

### Step 4: 给出"第一个小时"计划
告诉用户接下来60分钟要做的事，拆解成15分钟一段。

## 代码风格要求

为新手写的代码必须：
- 有中文注释解释关键步骤
- 变量名语义化，一看就懂
- 不要过度工程化，能工作就行
- 在关键位置加上 `# TODO: 未来可以...` 的扩展提示
