import os

from dotenv import load_dotenv
from fastapi import FastAPI

# Load environment variables from .env file
load_dotenv()

app = FastAPI()


@app.get("/")
def index():
    return {"status": "Alive"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, port=int(os.environ.get("PORT", 7777)), host="0.0.0.0")
