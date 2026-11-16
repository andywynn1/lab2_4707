# Part C 任务清单

- [x] 阅读 handout，确认 A/B 分支关系。
- [x] 从包含 A+B 的 `part-b` 建立本地 `part-c` 分支。
- [x] 修复 PinBuffer 时间戳赋值的锁保护。
- [x] 将日志和内存释放移出 buffer header 自旋锁。
- [x] 加入时间戳变化和 pin 状态变化的重试检查。
- [x] 在 pin 和内容锁保护下读取旧页空间，成功取得 victim 后再打印。
- [x] 删除已不用的 clock/ring 选择辅助函数。
- [x] 完成 macOS 编译、安装及官方 10,000 行数据测试。
- [x] 完成算法边界测试、2,000 组候选集合测试和内存检查。
- [x] 完成四客户端并发测试和 4,847 条淘汰日志校验。
- [x] 填写三名组员的 solution.txt，补充 README 和测试报告。
- [x] 准备 CSE 可复用的构建/测试脚本。
- [x] 按 handout 生成并校验 lab2.zip 的五个文件。
- [x] 在 CSE Linux (`csel-remote-lnx-01`, GCC 15.2) 完成全量构建、测试和 5,118 条日志校验。
- [x] 修复 GCC 15 默认 C23 模式与 PostgreSQL 16.0 的构建兼容问题（显式 GNU C99）。

当前更改保存在本地和 CSE 验证目录，没有 push、合并远程 PR 或提交到 Canvas。

## CSE 验证记录

运行目录：`/export/scratch/wu001664-lab2.sovfHW/run-c99`。
日志备份：`/home/wu001664/lab2-cse-results-sovfHW/results-c99.tar.gz`。
详细结果见 `TEST_RESULTS.md`；交付工具包包含补丁、测试脚本和两平台证据。
