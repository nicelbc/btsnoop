# 性能基线文档

## 1. 概述

本文档定义性能测试方法、基线数据和回归判定规则。每次 PR 自动运行 benchmark，与基线对比检测回归。

## 2. 测试环境标准

### 2.1 CI Benchmark 环境

| 配置项   | 规格                    |
|----------|------------------------|
| CPU      | 4 核 x86_64            |
| 内存     | 16 GB                  |
| OS       | Ubuntu 22.04           |
| Rust     | stable latest          |
| 隔离     | 独占 runner，无并行任务 |

### 2.2 本地 Benchmark 注意事项

- 关闭后台重载应用
- 使用 `--release` 编译
- 连续跑 3 次取中位数
- 笔记本确保接电源

## 3. Benchmark 用例定义

### 3.1 文件解析性能

| ID    | 用例名              | 输入                    | 测量项       | 基线目标    |
|-------|---------------------|-------------------------|--------------|-------------|
| BP-01 | 解析 1MB 文件       | 1MB btsnoop (~5000 包)  | 耗时         | < 10ms      |
| BP-02 | 解析 10MB 文件      | 10MB btsnoop (~50000 包)| 耗时         | < 100ms     |
| BP-03 | 解析 100MB 文件     | 100MB btsnoop           | 耗时         | < 1s        |
| BP-04 | 解析吞吐率          | 100MB 文件              | MB/s         | ≥ 100 MB/s  |

### 3.2 单包解码性能

| ID    | 用例名              | 输入                    | 测量项       | 基线目标    |
|-------|---------------------|-------------------------|--------------|-------------|
| BD-01 | HCI Command 解码    | Reset 命令 (3字节)      | 单次耗时     | < 100ns     |
| BD-02 | HCI Event 解码      | Cmd_Complete (7字节)    | 单次耗时     | < 150ns     |
| BD-03 | L2CAP + ATT 解码    | ATT Write (完整栈)      | 单次耗时     | < 500ns     |
| BD-04 | AVDTP SET_CONFIG 解码| 含 Codec Capability     | 单次耗时     | < 800ns     |
| BD-05 | 全栈解码 (最深)     | ACL→L2CAP→AVDTP→Codec  | 单次耗时     | < 1μs       |
| BD-06 | 1000 包批量解码     | 混合类型                | 耗时         | < 1ms       |

### 3.3 过滤引擎性能

| ID    | 用例名              | 输入                       | 测量项    | 基线目标   |
|-------|---------------------|----------------------------|-----------|------------|
| BF-01 | 编译简单过滤        | `hci.type == command`      | 编译耗时  | < 50μs    |
| BF-02 | 编译复杂过滤        | 3 层嵌套 AND/OR            | 编译耗时  | < 200μs   |
| BF-03 | 执行过滤 10万包     | 简单条件                   | 耗时      | < 30ms    |
| BF-04 | 执行过滤 10万包     | 复杂 AND/OR 组合           | 耗时      | < 80ms    |
| BF-05 | 执行过滤 100万包    | 简单条件                   | 耗时      | < 300ms   |
| BF-06 | contains 文本搜索   | 10万包搜索文本             | 耗时      | < 100ms   |

### 3.4 内存占用

| ID    | 用例名              | 输入                    | 测量项       | 基线目标       |
|-------|---------------------|-------------------------|--------------|---------------|
| BM-01 | 10万包内存占用      | 加载后稳态              | RSS          | < 150 MB      |
| BM-02 | 100万包内存占用     | 加载后稳态              | RSS          | < 1.2 GB      |
| BM-03 | 解析时峰值内存      | 100MB 文件解析过程      | Peak RSS     | < 500 MB      |
| BM-04 | 空闲会话内存        | 创建会话无数据          | RSS 增量     | < 1 MB        |

### 3.5 前端性能

| ID    | 用例名              | 条件                    | 测量项       | 基线目标      |
|-------|---------------------|-------------------------|--------------|--------------|
| BU-01 | 10万包列表渲染      | 虚拟滚动               | FPS          | ≥ 60fps      |
| BU-02 | 快速滚动 10万包     | 持续快速滚动 5s        | 白屏率       | 0%           |
| BU-03 | 过滤响应时间        | 10万包应用过滤         | 列表更新耗时 | < 200ms      |
| BU-04 | 包详情加载          | 点击展开协议树         | 渲染耗时     | < 50ms       |
| BU-05 | 首屏加载            | 空状态                 | LCP          | < 500ms      |
| BU-06 | WebSocket 批量更新  | 100包/批 × 20批/s      | 帧率         | ≥ 55fps      |

## 4. Benchmark 实现

### 4.1 后端 Benchmark (Criterion)

```rust
// benches/parse_benchmark.rs
use criterion::{criterion_group, criterion_main, Criterion, BenchmarkId, Throughput};

fn bench_parse_file(c: &mut Criterion) {
    let data_1mb = include_bytes!("../testdata/bench_1mb.btsnoop");
    let data_10mb = include_bytes!("../testdata/bench_10mb.btsnoop");

    let mut group = c.benchmark_group("file_parse");

    group.throughput(Throughput::Bytes(data_1mb.len() as u64));
    group.bench_with_input(BenchmarkId::new("parse", "1MB"), data_1mb, |b, data| {
        b.iter(|| parse_btsnoop(data))
    });

    group.throughput(Throughput::Bytes(data_10mb.len() as u64));
    group.bench_with_input(BenchmarkId::new("parse", "10MB"), data_10mb, |b, data| {
        b.iter(|| parse_btsnoop(data))
    });

    group.finish();
}

fn bench_decode_single(c: &mut Criterion) {
    let mut group = c.benchmark_group("single_decode");

    let hci_cmd = &[0x01, 0x03, 0x0C, 0x00];  // Reset
    group.bench_function("hci_command", |b| {
        b.iter(|| decode_packet(hci_cmd, 0))
    });

    let full_stack = build_att_write_packet();  // ACL→L2CAP→ATT
    group.bench_function("full_stack_att", |b| {
        b.iter(|| decode_packet(&full_stack, 0))
    });

    let avdtp_setconf = build_avdtp_set_config();
    group.bench_function("avdtp_set_config", |b| {
        b.iter(|| decode_packet(&avdtp_setconf, 0))
    });

    group.finish();
}

fn bench_filter(c: &mut Criterion) {
    let packets = load_test_packets(100_000);

    let mut group = c.benchmark_group("filter");

    let simple = compile_filter("hci.type == command").unwrap();
    group.bench_function("simple_100k", |b| {
        b.iter(|| packets.iter().filter(|p| simple(p)).count())
    });

    let complex = compile_filter("hci.type == acl && l2cap.cid == 0x0004 && att.opcode == 0x12").unwrap();
    group.bench_function("complex_100k", |b| {
        b.iter(|| packets.iter().filter(|p| complex(p)).count())
    });

    group.finish();
}

criterion_group!(benches, bench_parse_file, bench_decode_single, bench_filter);
criterion_main!(benches);
```

### 4.2 内存 Benchmark

```rust
// benches/memory_benchmark.rs
use peak_alloc::PeakAlloc;

#[global_allocator]
static PEAK_ALLOC: PeakAlloc = PeakAlloc;

#[test]
fn measure_memory_100k_packets() {
    PEAK_ALLOC.reset_peak_usage();
    let data = include_bytes!("../testdata/bench_100k.btsnoop");
    let session = parse_and_store(data);

    let current = PEAK_ALLOC.current_usage_as_mb();
    let peak = PEAK_ALLOC.peak_usage_as_mb();

    assert!(current < 150.0, "100k packets steady state: {:.1}MB > 150MB", current);
    assert!(peak < 300.0, "100k packets peak: {:.1}MB > 300MB", peak);

    println!("100k packets: current={:.1}MB, peak={:.1}MB", current, peak);
}
```

### 4.3 前端 Benchmark (Lighthouse + 自定义)

```typescript
// tests/performance/scroll.bench.ts
import { bench, describe } from 'vitest';

describe('PacketList scroll performance', () => {
  bench('render 100k packets initial', async () => {
    const packets = generateMockPackets(100_000);
    const { container } = render(<PacketList packets={packets} />);
    // 验证虚拟列表只渲染可视区
    const rows = container.querySelectorAll('[data-row]');
    expect(rows.length).toBeLessThan(100);
  });

  bench('filter 100k packets', async () => {
    const store = createTestStore(100_000);
    store.setFilter('hci.type == command');
    // 验证过滤完成时间
  });
});
```

## 5. 基线管理

### 5.1 基线存储

```
benchmarks/
├── baseline.json           # 当前基线数据
├── history/
│   ├── v0.1.0.json         # 历史版本基线
│   ├── v0.2.0.json
│   └── ...
└── reports/
    └── latest_comparison.md # 最近一次对比报告
```

### 5.2 基线格式

```json
{
  "version": "0.1.0",
  "date": "2026-05-27",
  "environment": "CI runner 4-core",
  "results": {
    "BP-01": {"value": 8.2, "unit": "ms"},
    "BP-04": {"value": 122, "unit": "MB/s"},
    "BD-01": {"value": 85, "unit": "ns"},
    "BD-05": {"value": 780, "unit": "ns"},
    "BF-03": {"value": 25, "unit": "ms"},
    "BM-01": {"value": 120, "unit": "MB"}
  }
}
```

### 5.3 基线更新规则

- 每个版本发布时刷新基线
- 有性能优化合入时可更新基线
- 更新基线需要 PR + Review
- 不允许因为性能退步而"更新基线"来绕过

## 6. 回归判定规则

### 6.1 自动判定

| 回归幅度      | 判定     | CI 行为        |
|---------------|----------|----------------|
| < 10%         | PASS     | 绿灯，正常合入 |
| 10% ~ 20%    | WARNING  | 黄灯，PR 中标注 |
| 20% ~ 50%    | REVIEW   | 需要在 PR 中说明原因，Reviewer 确认 |
| > 50%         | FAIL     | 红灯，阻塞合入 |

### 6.2 回归幅度计算

```
regression_percent = (new_value - baseline) / baseline * 100%

对于耗时类指标：new > baseline 为回归
对于吞吐类指标：new < baseline 为回归
对于内存类指标：new > baseline 为回归
```

### 6.3 例外情况

以下情况允许性能回归：
- 新增安全检查（边界校验）导致的 <20% 回归
- 功能正确性修复导致的回归（优先正确性）
- 明确标注为 tradeoff 的设计决策

但必须在 PR 描述中说明原因和幅度。

## 7. 性能报告格式

每次 CI 生成的对比报告：

```markdown
## Performance Report — PR #42

Baseline: v0.1.0 (2026-05-20)
Environment: CI runner 4-core

| ID    | Benchmark            | Baseline  | Current   | Change   | Status  |
|-------|---------------------|-----------|-----------|----------|---------|
| BP-01 | Parse 1MB           | 8.2ms     | 8.5ms     | +3.6%    | ✅ PASS |
| BD-05 | Full stack decode   | 780ns     | 820ns     | +5.1%    | ✅ PASS |
| BF-03 | Filter 100k simple  | 25ms      | 24ms      | -4.0%    | ✅ PASS |
| BM-01 | Memory 100k packets | 120MB     | 118MB     | -1.7%    | ✅ PASS |

Overall: ✅ All benchmarks within acceptable range
```

## 8. 性能优化指引

当性能不达标时的排查顺序：

### 8.1 解析性能

1. `perf record` 热点分析
2. 检查不必要的内存分配（`Vec::push` 是否有 realloc）
3. 检查字符串格式化是否在热路径
4. 考虑 SIMD 加速字节搜索

### 8.2 解码性能

1. 查表是否用了 HashMap（考虑切换为数组索引或 phf）
2. 是否有不必要的 clone/allocation
3. SmallVec 替代 Vec 用于小集合

### 8.3 过滤性能

1. 索引快速路径是否生效
2. 过滤函数是否被正确编译（不是每包重新解析 AST）
3. 短路求值是否正确

### 8.4 前端性能

1. 虚拟列表 overscan 是否过大
2. 是否有不必要的 re-render（React DevTools Profiler）
3. WebSocket 消息处理是否批量更新 state
4. 大数组操作是否在 Worker 中
