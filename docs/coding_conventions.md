# 编码规范与约束文档

## 1. 概述

本文档定义项目的编码规范、质量要求和开发流程约束，所有代码贡献必须遵守。

## 2. 后端编码规范 (Rust)

### 2.1 代码风格

- 使用 `rustfmt` 默认配置格式化
- 使用 `clippy` 并修复所有警告 (`cargo clippy -- -D warnings`)
- 行宽上限：100 字符
- 缩进：4 空格

### 2.2 命名规范

| 类别       | 风格         | 示例                     |
|-----------|-------------|--------------------------|
| 类型/结构体 | PascalCase  | `PacketStore`            |
| 函数/方法  | snake_case  | `decode_hci_event`       |
| 常量       | UPPER_SNAKE | `MAX_PACKET_SIZE`        |
| 模块       | snake_case  | `protocol_decoder`       |
| 枚举变体   | PascalCase  | `Direction::Sent`        |
| trait      | PascalCase  | `ProtocolDecoder`        |

### 2.3 错误处理

- 使用 `thiserror` 定义错误类型
- 禁止在库代码中使用 `unwrap()` / `expect()`（测试代码除外）
- API handler 中使用统一错误响应格式
- 解码错误不应 panic，应返回 partial result + error list

```rust
// 正确：返回解码结果 + 错误列表
pub fn decode(&self, data: &[u8]) -> DecodeResult {
    DecodeResult {
        layers: partial_layers,
        errors: vec!["Truncated at offset 12".into()],
    }
}

// 错误：直接 panic
pub fn decode(&self, data: &[u8]) -> DecodedLayer {
    let value = data[12]; // panic if out of bounds!
}
```

### 2.4 安全性要求

- 所有外部输入（文件数据、网络数据）必须做边界检查
- 使用 `get()` / `checked_*` 而非直接索引
- 解析时设置最大递归深度（防止恶意构造的数据栈溢出）
- 禁止 `unsafe` 代码（除非有性能瓶颈且已 benchmark 证明必要）

```rust
// 正确
let value = data.get(offset..offset+2)
    .ok_or(DecodeError::Truncated { offset, expected: 2 })?;

// 错误
let value = &data[offset..offset+2]; // panic on OOB
```

### 2.5 并发安全

- 共享状态使用 `Arc<RwLock<T>>` 或 `Arc<Mutex<T>>`
- 优先使用消息传递 (`tokio::sync::mpsc`) 而非共享状态
- 禁止持有锁跨 `.await` 点
- `PacketStore` 的 append 操作必须保证原子性

### 2.6 性能要求

- 单包解码时间 < 1ms（benchmark 验证）
- 内存分配最小化：解码器复用 buffer
- 大量包遍历时使用迭代器，避免中间集合
- 热路径禁止动态分配（使用 `SmallVec` / 栈数组）

## 3. 前端编码规范 (TypeScript + React)

### 3.1 代码风格

- 使用 ESLint + Prettier，配置统一
- 行宽上限：100 字符
- 缩进：2 空格
- 分号：强制使用
- 引号：单引号

### 3.2 命名规范

| 类别       | 风格         | 示例                     |
|-----------|-------------|--------------------------|
| 组件       | PascalCase  | `PacketList.tsx`         |
| hook       | camelCase   | `usePacketFilter`        |
| 工具函数   | camelCase   | `formatTimestamp`        |
| 常量       | UPPER_SNAKE | `MAX_DISPLAY_PACKETS`   |
| 类型/接口  | PascalCase  | `PacketSummary`          |
| CSS 类名   | kebab-case  | `packet-list-row`        |

### 3.3 组件规范

- 函数组件 + Hooks，禁止 class 组件
- Props 类型必须显式定义 interface
- 组件文件单一职责，不超过 300 行
- 重渲染敏感组件使用 `React.memo` + `useMemo`/`useCallback`

```typescript
// 正确
interface PacketRowProps {
  packet: PacketSummary;
  selected: boolean;
  onClick: (index: number) => void;
}

const PacketRow = React.memo<PacketRowProps>(({ packet, selected, onClick }) => {
  // ...
});
```

### 3.4 状态管理

- 全局状态使用 Zustand（轻量、TypeScript 友好）
- 组件局部状态用 `useState`
- 服务端状态用 `@tanstack/react-query`（如果有 REST 请求）
- 禁止 prop drilling 超过 3 层

### 3.5 性能约束

- 包列表必须使用虚拟滚动，DOM 节点不超过可视区 + 50
- WebSocket 消息处理使用 `requestAnimationFrame` 批量更新
- 大数组操作在 Web Worker 中执行
- 初始加载 bundle size < 500KB (gzipped)

### 3.6 TypeScript 严格模式

```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "exactOptionalPropertyTypes": true
  }
}
```

禁止使用 `any`、`as any`、`@ts-ignore`。

## 4. 通用约束

### 4.1 Git 规范

**分支命名：**
```
feature/xxx    -- 新功能
fix/xxx        -- 修复
refactor/xxx   -- 重构
docs/xxx       -- 文档
```

**Commit Message 格式：**
```
<type>(<scope>): <subject>

type: feat / fix / refactor / docs / test / chore
scope: parser / decoder / frontend / api / filter / infra
```

示例：
```
feat(decoder): add AVDTP signal ID decoding
fix(parser): handle truncated packet at EOF
refactor(frontend): extract HexView to standalone component
```

### 4.2 测试要求

| 类型       | 覆盖范围           | 要求              |
|-----------|-------------------|-------------------|
| 单元测试   | 解码器、过滤器    | 每个协议≥20个用例 |
| 集成测试   | API 端点          | 覆盖所有端点      |
| 解码验证   | 与 Wireshark 对比 | 标准 btsnoop 文件 |
| 性能测试   | 解析速度、内存    | P0 完成后建立基线 |
| 前端测试   | 组件渲染          | 关键交互路径      |

**解码器测试数据来源：**
- Wireshark 导出的已知正确解码
- 手工构造的边界用例
- Android CTS 中的蓝牙测试抓包

### 4.3 文档要求

- 公开 API 必须有 OpenAPI/Swagger 文档
- 解码器每新增一个协议必须更新 `protocol_decode_spec.md`
- 代码中不写注释，除非解释 WHY（不解释 WHAT）

### 4.4 依赖管理

**后端：**
- 最小化依赖，优先标准库
- 禁止引入含 `unsafe` 的未经审计 crate
- `Cargo.lock` 必须提交

**前端：**
- 使用 pnpm（确定性安装）
- 禁止引入 > 100KB 的 UI 框架
- `pnpm-lock.yaml` 必须提交

### 4.5 兼容性约束

- 后端最低支持 Rust 1.75 stable
- 前端最低支持浏览器：Chrome 90, Firefox 90, Edge 90, Safari 15
- btsnoop 格式：兼容 v1 格式，Datalink Type 1001/1002/2001

## 5. 安全约束

### 5.1 输入验证

| 输入源       | 验证规则                            |
|-------------|-------------------------------------|
| 上传文件     | Magic bytes 校验、大小限制、超时    |
| 过滤表达式   | 长度限制、解析超时、嵌套深度限制    |
| WebSocket 帧 | 大小限制、速率限制                  |
| URL 参数     | 类型校验、范围校验                  |

### 5.2 资源限制

- 单会话内存上限：2GB
- 单次解析超时：5 分钟
- WebSocket 连接数上限：200
- 文件上传速率限制：2 req/s per IP

### 5.3 禁止事项

- 禁止执行用户上传文件中的任何代码
- 禁止将用户数据写入持久存储（内存 only）
- 禁止在日志中输出原始包数据（仅输出摘要）
- 禁止将会话数据跨用户共享（除非显式协作模式）

## 6. CI/CD 约束

### 6.1 PR 合入条件

- [ ] `cargo fmt --check` 通过
- [ ] `cargo clippy -- -D warnings` 通过
- [ ] `cargo test` 全部通过
- [ ] `pnpm lint` 通过
- [ ] `pnpm type-check` 通过
- [ ] `pnpm test` 通过
- [ ] 无新增 `unsafe` 代码（除非有 justification）
- [ ] 无新增 `any` 类型（除非有 justification）

### 6.2 自动化检查

```yaml
# .github/workflows/ci.yml 核心步骤
- cargo fmt --check
- cargo clippy -- -D warnings
- cargo test
- cargo bench (性能回归检测)
- pnpm lint
- pnpm type-check
- pnpm test
- pnpm build (确保可构建)
```
