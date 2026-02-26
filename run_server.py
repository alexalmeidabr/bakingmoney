from app.asyncio_bootstrap import bootstrap_asyncio

bootstrap_asyncio()

import uvicorn


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
