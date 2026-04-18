"""
Monad: an LLM chooses when to call telos_search, telos_write, and http_get.
All runtime settings live in config.yaml; only API keys use environment variables.
"""

from monad_runtime.app import main


if __name__ == "__main__":
    main()
