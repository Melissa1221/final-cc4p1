# Guion de la demo en vivo (paso a paso, desde cero)

Como correr todo el sistema en la expo, con las 3 laptops. Sigue el orden. Cada
integrante tiene su rol. Tiempo total: ~5-7 minutos.

## Roles

| Integrante | Laptop | Corre |
|---|---|---|
| Melissa | Laptop 1 (Java) | Nodo Java + servidor de video + camara + Vigilante desktop |
| Andrew | Laptop 2 (Python) | Nodo Python |
| Junior | Laptop 3 (Go) | Nodo Go |

> La cámara, el servidor de video y el Vigilante corren en UNA sola laptop
> (Melissa). Los otros dos solo levantan su nodo. No hace falta que los tres
> tengan cámara.

---

## PASO 0 — Antes de empezar (una vez, ya en el salon)

**Las 3 laptops en la MISMA red WiFi.** Cada uno saca su IP:

- Mac: `ipconfig getifaddr en0`
- Windows: `ipconfig` (busca "IPv4" de la WiFi)

Anoten las 3 IP y acuerden esta lista (cambien las IP por las reales):

```
1:IP_MELISSA:9001 2:IP_ANDREW:9002 3:IP_JUNIOR:9003
```

**Todos usan la MISMA lista.** Solo cambia el numero de nodo (1, 2, 3) al inicio
de su comando. En este guion la escribimos como `LISTA`.

Cada uno abre una terminal en la carpeta del repo:

```bash
cd .../final/repo-setup
```

**IMPORTANTE — solo Melissa necesita el dataset y el modelo.** Andrew y Junior solo
levantan su nodo (el nodo Raft NO usa la CNN ni CIFAR, solo hace consenso). Andrew
y Junior NO descargan CIFAR ni entrenan nada.

Melissa (una sola vez): descarga el dataset y entrena. Desde `python/`:

```bash
cd python
mkdir -p datos && cd datos
curl -LO https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz
tar xzf cifar-10-python.tar.gz
cd ..
python3 cnn/entrenar_cifar.py 800
cd ..
```

Si Andrew o Junior ven el error "no encuentro datos/cifar-10-batches-py", es porque
intentaron entrenar: NO tienen que entrenar, solo levantar su nodo (paso 1).

---

## PASO 1 — Levantar los 3 nodos (los 3 integrantes, casi a la vez)

Cada uno en SU laptop, en SU terminal:

**Melissa (Laptop 1, Java):**
```bash
cd java && javac -cp lib/flatlaf-3.4.1.jar -d out src/raft/*.java
java -cp out raft.ArrancarNodo 1 LISTA
```

**Andrew (Laptop 2, Python):**
```bash
cd python
python3 raft/arrancar.py 2 LISTA
```

**Junior (Laptop 3, Go):**
```bash
cd go
go run ./cmd/arrancar-nodo 3 LISTA
```

En una de las 3 terminales aparecera `*** soy LIDER en term 1 ***`. **Ese es el
lider.** Digan en voz alta cual laptop quedo de lider (importante para el paso 5).

Si no eligen lider: revisen que las 3 IP sean correctas y que esten en la misma
WiFi (a veces el firewall de Windows bloquea; permitir el puerto o desactivarlo).

---

## PASO 2 — Servidor de video (Melissa, nueva terminal)

```bash
cd python
python3 video/servidor_video.py 9500
```

Debe decir `servidor de video escuchando`. Emite los frames a las camaras.

---

## PASO 3 — La camara reconociendo (Melissa, nueva terminal)

Dos opciones. Elige UNA:

**Opcion A — camara REAL (webcam en vivo):** abre tu camara, reconoce lo que ve.

```bash
cd python
python3 testeo/camara_real.py 1 LISTA
```

Muestrale FOTOS REALES (no dibujos) de las clases que mejor reconoce: **auto,
avion, camion, caballo**. Centra el objeto en el cuadro azul. Reconoce cada 3s.

**Opcion B — modo demo seguro (no falla):** muestra objetos del dataset y los
reconoce correcto. Usa esta si la webcam falla o para ir a la segura.

```bash
cd python
python3 testeo/camara_demo.py 1 LISTA
```

Sea cual sea, vas a ver una ventana "Camara 1" con "Detecto: X" y cada deteccion
se inserta al cluster.

---

## PASO 4 — El Vigilante mostrando el registro (Melissa, nueva terminal)

**Desktop:**
```bash
./scripts/correr-vigilante.sh LISTA
```

Abre la ventana con el registro: foto, tipo, camara, fecha/hora, refrescandose en
vivo mientras la camara detecta. Este es el resultado visible.

**Movil (opcional, si lo van a mostrar):** abre `mobile/` en Android Studio, corre
en el emulador, y en la app pon los nodos con la IP de Melissa (o `10.0.2.2` si el
emulador esta en la misma Mac).

---

## PASO 5 — Tolerancia a fallos: el momento estrella (los 3)

Esto es lo que mas evalua el profe. Con todo corriendo:

1. La laptop que quedo de LIDER (paso 1) **corta su nodo** con `Ctrl+C` (o cierra
   la laptop).
2. En unos segundos, otra laptop dira `*** soy LIDER en term 2 ***`. **Se reeligio
   lider entre las maquinas que quedan.**
3. El Vigilante (paso 4) sigue mostrando el registro completo: **no se perdio nada**.
4. La camara puede seguir insertando y aparece en el nuevo lider.

Digan en voz alta: "matamos el lider, el sistema reeligio otro y el registro sigue
consistente". Eso demuestra el consenso Raft real entre 3 maquinas distintas.

---

## PASO 6 — Cerrar

`Ctrl+C` en cada terminal para apagar los nodos.

---

## Que decir mientras corre (resumen para la expo)

- "Tres nodos en tres lenguajes (Java, Python, Go), un integrante por maquina, todos
  hablando el mismo protocolo por **sockets nativos**, sin frameworks."
- "La camara reconoce con una **CNN que entrenamos desde cero en NumPy** (CIFAR-10,
  objetos reales). El modelo se entreno antes y corre sin internet."
- "Cada deteccion se replica en los 3 nodos con **Raft**: solo se confirma cuando la
  mayoria la copio, por eso sobrevive a que caiga una maquina."
- "Si matamos el lider, los otros reeligen uno y el registro sigue: eso es la
  tolerancia a fallos del consenso."

## Si algo falla en vivo (plan B)

- La webcam no reconoce bien -> usa `camara_demo.py` (modo seguro).
- Una laptop no conecta -> revisa IP y WiFi; en el peor caso corre los 3 nodos en
  una sola laptop con `1:127.0.0.1:9001 2:127.0.0.1:9002 3:127.0.0.1:9003` (sigue
  demostrando el consenso, aunque no en 3 maquinas fisicas).
- El Vigilante dice "(sin imagen)" en detecciones viejas: es normal, las nuevas si
  traen foto.

## Clases que reconoce el modelo

avion, auto, pajaro, gato, ciervo, perro, rana, caballo, barco, camion.
**No reconoce personas.** Las que mejor acierta: auto, avion, camion, caballo, rana.
