from openai import AsyncOpenAI
from openai._utils._proxy import LazyProxy
from pydantic import BaseModel, Field
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.chat.chat_completion_tool_param import ChatCompletionToolParam
from openai.types.shared_params.function_definition import FunctionDefinition
from abc import ABC, abstractmethod
import typing as tp
import typing_extensions as tpe

ChatModel: tpe.TypeAlias = tp.Literal[
    "llama-3.3-70b-versatile",
    "llama-3.2-90b-vision",
    "llama3-8b-8192",
    "llama-3.2-11b-vision",
]
T = tp.TypeVar("T")
P = tp.ParamSpec("P")


class Tool(BaseModel, LazyProxy[AsyncOpenAI], ABC):
    @classmethod
    def definition(cls) -> ChatCompletionToolParam:
        return ChatCompletionToolParam(
            type="function",
            function=FunctionDefinition(
                name=cls.__name__,
                description=cls.__doc__ or "[No description]",
                parameters=cls.model_json_schema().get("properties", {}),
            ),
        )

    @abstractmethod
    async def run(
        self,
    ) -> str:
        raise NotImplementedError()

    def __load__(self):
        return AsyncOpenAI(
            base_url="https://uacida0z2l2pgw-8080.proxy.runpod.net/v1", api_key="sk-proj-1234567890"
        )


class Agent(Tool):
    model: ChatModel = Field(default="llama-3.3-70b-versatile")
    messages: list[ChatCompletionMessageParam] = Field(default_factory=list)
    max_tokens: int = Field(default=8000)

    @property
    def images(self):
        client = AsyncOpenAI(
            base_url="https://wwjz8q6r0fcqyj-5000.proxy.runpod.net/v1",
            api_key="sk-proj-1234567890",
        )
        return client.images

    @property
    def audio(self):
        client = AsyncOpenAI(
            base_url="https://mgw5s3ku3olqts-5000.proxy.runpod.net/v1",
            api_key="sk-proj-1234567890",
        )
        return client.audio

    @property
    def fine_tuning(self):
        client = AsyncOpenAI(
            base_url="https://mgw5s3ku3olqts-8000.proxy.runpod.net/v1",
            api_key="sk-proj-1234567890",
        )
        return client.fine_tuning

    async def execute(self) -> tp.AsyncGenerator[str, None]:
        client = self.__load__()
        response = await client.chat.completions.create(
            model=self.model,
            tools=[d.definition() for d in Tool.__subclasses__()],
            tool_choice="auto",
            messages=self.messages,
            temperature=0.2,
            max_tokens=self.max_tokens,
            stream=False,
        )
        tool_calls = response.choices[0].message.tool_calls
        if not tool_calls:
            content = response.choices[0].message.content
            if content:
                yield content
            else:
                raise ValueError("No content found")
        else:
            for tool_call in tool_calls:
                for d in Tool.__subclasses__():
                    if d.__name__ == tool_call.function.name:
                        tool = d.model_validate_json(tool_call.function.arguments)
                        yield await tool.run()
                        return
            raise ValueError("No tool calls found")

    async def run(self) -> str:
        data = ""
        async for line in self.execute():
            data += line
        return data
