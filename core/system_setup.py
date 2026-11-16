from core.engine_setup import create_engine_manager
from core.director_bridge import DirectorBridge
from master_director import MasterNarrationDirector

def create_director_bridge():
    engine_manager = create_engine_manager()
    director = MasterNarrationDirector()

    return DirectorBridge(
        engine_manager=engine_manager,
        director=director,
    )

if __name__ == "__main__":
    bridge = create_director_bridge()

    result = bridge.analyze_and_resolve(
        "Are you ready for the next chapter?"
    )

    print("DIRECTOR BRIDGE READY")
    print("Speed:", result.speed)
    print("Pitch:", result.pitch)
    print("Volume:", result.volume)
    print("Reasons:", result.reasons)
