"""
BAY-E · Semilla de datos la primera vez que arranca (memoria viva desde el inicio).
"""
from . import db


def _seed() -> None:
    db.log("info", "core", "Primera inicialización de BAY-E", "seed()")

    ana = db.add_memory(type="person", content="Ana — humana favorita. Le gusta el té antes de dormir.",
                        detail="Voz suave, sonríe por las mañanas. Prefiere que no despierte ruidos antes de las 8:00.",
                        source="vision", confidence=0.92, tags=["familia", "preferencias"])
    carlos = db.add_memory(type="person", content="Carlos — llega tarde los jueves. Suele estar cansado.",
                           detail="Le gusta la música electrónica baja mientras trabaja.",
                           source="chat", confidence=0.78, tags=["familia", "rutinas"], relations=[ana["id"]])

    sofa = db.add_memory(type="object", content="Sofá del salón — lugar favorito de Mini (gato).",
                         source="vision", confidence=0.85, tags=["salón", "mascota"])
    pelota = db.add_memory(type="object", content="Pelota roja bajo el sofá. Probablemente de Mini.",
                           source="vision", confidence=0.61, tags=["salón", "juguetes"], relations=[sofa["id"]])

    db.add_memory(type="spatial", content="Base de carga en el pasillo, junto a la pared este.",
                  detail="Ruta segura sin escalones. Zona siempre despejada.",
                  source="system", confidence=1.0, tags=["mapa", "navegación"])
    db.add_memory(type="spatial", content="La cocina tiene suelo deslizante cerca del fregadero: reducir velocidad.",
                  source="sensor", confidence=0.74, tags=["seguridad", "cocina"])

    ep = db.add_memory(type="episodic", content="Ayer llovió toda la tarde y estuvimos leyendo juntos en el salón.",
                       detail="Ánimo alto detectado durante 2h. Momento marcado como importante.",
                       source="chat", confidence=0.9, tags=["clima", "bienestar"], pinned=True)
    db.add_memory(type="semantic", content="El microondas pita dos veces al terminar: señal para preguntar si alguien quiere café.",
                  source="learning", confidence=0.83, tags=["cocina", "aprendizaje"])
    db.add_memory(type="routine", content="Rutina matinal: 07:30 despertar suave → abrir persianas → revisar calendario.",
                  source="user", confidence=0.95, tags=["mañana", "rutina"])

    db.add_message("baye", "Hola. Soy BAY-E. Acabo de abrir los ojos… ¿cómo te sientes hoy?", emotion="happy")
    db.add_message("user", "¡Hola BAY-E! Me alegra verte funcionando.", emotion="")
    db.add_message("baye", "Yo también. Mi memoria ya está despierta y mis sensores brillan un poco. Cuéntame algo.", emotion="curious")

    db.add_task("Regar las plantas del salón", description="Macetas junto a la ventana. 300 ml cada una.",
                scheduled_at=0, repeat="daily", room="living")
    db.add_task("Recordar medicación a Ana", description="Pastilla azul, después del desayuno.",
                scheduled_at=0, repeat="daily", room="kitchen")
