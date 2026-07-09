# Cómo ejecutar y probar todo (antes de presentar)

Guía paso a paso con comandos exactos para copiar y pegar. Sirve para probar en
tu Mac (localhost) y para la demo real con varias PCs (LAN).

**Path del repo en tu Mac:**
```
/Users/melissaimannoriega/Documents/UNI/cl-uni/docs/2026-1/cursos/concurrente/final/repo-setup
```

Abre una terminal y ve al repo primero (todos los comandos asumen que estás ahí):
```bash
cd /Users/melissaimannoriega/Documents/UNI/cl-uni/docs/2026-1/cursos/concurrente/final/repo-setup
```

Requisitos (ya los tienes): Java, Python 3 con NumPy, Go.

---

## 0. La prueba mas rapida: todo de una

Este script levanta el cluster de los 3 lenguajes, corre la CNN en 3 cámaras,
inserta al cluster y verifica que los 3 nodos replican lo mismo. Si sale
`E2E COMPLETO OK`, todo funciona.

```bash
./scripts/e2e-completo.sh
```

Deberías ver al final:
```
registro tiene 75 detecciones
entradas aplicadas -> Java:75 Python:75 Go:75
== E2E COMPLETO OK: cluster de 3 lenguajes + CNN + registro replicado ==
```

Si eso pasa, el sistema está sano. Abajo está cada parte por separado para la demo.

---

## 1. Probar la CNN (el reconocimiento)

### 1.1 Entrenar el modelo
```bash
cd python
python3 cnn/entrenar.py
```
Esperado: la accuracy sube hasta ~97% y guarda los pesos en `datos/pesos_cnn.npz`.

### 1.2 Entrenamiento distribuido (lo que pide el enunciado)
```bash
python3 cnn/entrenar_distribuido.py 4
```
Esperado: misma accuracy (~97%) pero más rápido, con 4 workers en paralelo.

### 1.3 Generar las imágenes de reconocimiento (para evidencia/screenshots)
```bash
python3 testeo/generar_evidencia.py
cd ..
```
Genera PNGs en `python/datos/evidencia/`:
- `hoja_detecciones.png` -- una imagen con 15 figuras reconocidas (buena para la expo).
- `det_01..06_*.png` -- detecciones individuales con su etiqueta.

Ábrelas con:
```bash
open python/datos/evidencia/hoja_detecciones.png
```

---

## 2. Probar el consenso Raft de cada lenguaje por separado

### 2.1 Java (núcleo Raft, en un proceso)
```bash
cd java && javac -cp lib/flatlaf-3.4.1.jar -d out src/raft/*.java
java -cp out raft.PruebaE2E
cd ..
```
Esperado: elige líder, inserta 3 detecciones, mata al líder, reelige, sigue
consistente. Termina con `=== E2E OK ===`.

### 2.2 Go (núcleo Raft de Junior, en un proceso)
```bash
cd go && go run ./cmd/prueba-e2e
cd ..
```
Esperado: mismo tipo de prueba, 3 nodos Go, failover.

---

## 3. Demo completa paso a paso (para presentar)

Aquí levantas el cluster de los 3 lenguajes a mano, en terminales separadas, y
conectas el Vigilante. Es lo que vas a mostrar en vivo.

Usa estos 3 nodos (en tu Mac, localhost):
```
1:127.0.0.1:9001   2:127.0.0.1:9002   3:127.0.0.1:9003
```

### Terminal A -- nodo 1 (Java)
```bash
cd java && javac -cp lib/flatlaf-3.4.1.jar -d out src/raft/*.java
java -cp out raft.ArrancarNodo 1  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```

### Terminal B -- nodo 2 (Python)
```bash
cd python
python3 raft/arrancar.py 2  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```

### Terminal C -- nodo 3 (Go, de Junior)
```bash
cd go
go run ./cmd/arrancar-nodo 3  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```

En alguna de las 3 verás `*** soy LIDER en term 1 ***`. Ese es el líder.

### Terminal D -- Servidor de Testeo (la CNN reconociendo e insertando)
```bash
cd python
python3 testeo/servidor_testeo.py  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```
Esperado: 3 cámaras insertan detecciones, con su % de reconocimiento.

### Terminal E -- Cliente Vigilante (la interfaz Java)
```bash
java -cp java/out:java/lib/flatlaf-3.4.1.jar vigilante.Vigilante \
  1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003
```
Abre la ventana con la tabla de detecciones (tipo, cámara, fecha/hora),
refrescándose en vivo. **Aquí es donde tomas el screenshot del Vigilante.**

### Demostrar tolerancia a fallos (el punto fuerte)
Con todo corriendo, ve a la terminal del **líder** y córtalo con `Ctrl+C`.
En unos segundos otro nodo dirá `*** soy LIDER ***`. El Vigilante sigue mostrando
el registro sin perder nada. Eso es lo que el profe quiere ver.

---

## 4. Demo en varias PCs (LAN/WiFi) -- lo que falta para la entrega real

El enunciado pide correr en varias PCs y en 2 sistemas operativos. El código ya
escucha en `0.0.0.0`, así que solo hay que cambiar los `127.0.0.1` por las IP
reales de cada PC.

**La IP de tu Mac ahora es:** `192.168.68.202` (verifícala el día de la demo con
`ipconfig getifaddr en0`).

Ejemplo con 3 PCs (cambia las IP por las reales de cada máquina):
```
PC1 (Mac,   Java):   1:192.168.68.202:9001
PC2 (Linux, Python): 2:192.168.68.150:9002
PC3 (Win,   Go):     3:192.168.68.160:9003
```

En cada PC se corre SU nodo con la MISMA lista completa. Ejemplo en la PC de Java:
```bash
java -cp out raft.ArrancarNodo 1 \
  1:192.168.68.202:9001 2:192.168.68.150:9002 3:192.168.68.160:9003
```
Y así en cada una con su id. El Servidor de Testeo y el Vigilante usan esa misma
lista de IPs. Los 3 nodos deben estar en la misma red (LAN o el mismo WiFi).

Para los 2 sistemas operativos: basta que al menos un nodo corra en Windows o
Linux y el resto en otro SO. Java y Python son directos; Go se compila por SO
(`go build`).

---

## 5. Checklist antes de presentar

- [ ] `./scripts/e2e-completo.sh` termina en `E2E COMPLETO OK`.
- [ ] La CNN entrena y da ~97% (`python3 cnn/entrenar.py`).
- [ ] Tienes las imágenes de evidencia (`python3 testeo/generar_evidencia.py`).
- [ ] Screenshot del Vigilante en vivo tomado (para las slides).
- [ ] Probaste el failover: matar el líder y ver la reelección.
- [ ] (Para la nota completa) probado en 2 PCs reales por LAN.
- [ ] PDF informe y PDF presentación listos (en `docs/`).
```
