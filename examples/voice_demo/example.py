import asyncio
from gaia.voice.voice_manager import VoiceManager

async def main() -> None:
    manager = VoiceManager()
    print(manager.status().model_dump())
    result = await manager.synthesize("Hello, I am GAIA's synthetic voice identity.")
    print(result.model_dump())

if __name__ == "__main__":
    asyncio.run(main())
