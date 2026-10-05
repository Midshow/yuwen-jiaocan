"""命令行兼容入口；查询实现统一维护于 jiaocan 包。"""
from jiaocan.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
