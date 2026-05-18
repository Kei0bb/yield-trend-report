"""Windows 環境での起動スクリプト。
`uv run uvicorn` がスクリプト実行の問題で動かない場合はこちらを使用。

Usage:
    uv run python run.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
