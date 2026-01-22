import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

def get_normal_llm(temperature: float = 0) -> ChatOpenAI:
    return ChatOpenAI(
        temperature=temperature,
        model=os.getenv("AZURE_MODEL"),
        api_key=os.getenv("AZURE_API_KEY"),
        base_url=os.getenv("AZURE_URL")
    )

def get_embeddings_llm() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
            model=os.getenv("AZURE_EMBEDDING_MODEL"),
            base_url=os.getenv("AZURE_EMBEDDINGS_URL"),
            api_key=os.getenv("AZURE_EMBBEDINGS_KEY")
        )
    pass

