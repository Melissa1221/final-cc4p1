package entrenamiento;

import java.io.*;
import java.util.*;
import java.util.concurrent.*;

// Servidor de Entrenamiento (parte de Melissa, Java).
// Demuestra el requisito del enunciado: el entrenamiento se puede repartir entre
// nodos de manera paralela distribuida tipo CPU, y los pesos resultantes se
// persisten para su consumo posterior.
//
// Para que sea autocontenido y no dependa de datasets externos, entrena un
// clasificador lineal simple (un peso por clase) sobre datos sinteticos: cada
// clase tiene un centroide y las muestras son puntos alrededor. El punto clave a
// evaluar no es el modelo en si, sino que la CARGA se divide entre workers con
// hilos y el resultado se agrega y se guarda a disco.
//
// El reparto: el dataset se parte en shards, un hilo (worker) por shard calcula
// la suma parcial de cada clase, y al final se agregan las sumas para obtener el
// centroide (peso) de cada clase. Esto es un all-reduce basico hecho a mano.
public class Entrenador {

    final int numClases;
    final int dimension;
    final int muestrasPorClase;
    final int numWorkers;

    public Entrenador(int numClases, int dimension, int muestrasPorClase, int numWorkers) {
        this.numClases = numClases;
        this.dimension = dimension;
        this.muestrasPorClase = muestrasPorClase;
        this.numWorkers = numWorkers;
    }

    // Genera un dataset sintetico: cada clase gira en torno a un centroide propio.
    double[][] generarDatos(int[] etiquetas) {
        Random r = new Random(42);
        int total = numClases * muestrasPorClase;
        double[][] datos = new double[total][dimension];
        double[][] centroides = new double[numClases][dimension];
        for (int c = 0; c < numClases; c++)
            for (int d = 0; d < dimension; d++)
                centroides[c][d] = (c + 1) * 2.0 + r.nextGaussian() * 0.1;

        int idx = 0;
        for (int c = 0; c < numClases; c++) {
            for (int m = 0; m < muestrasPorClase; m++) {
                for (int d = 0; d < dimension; d++)
                    datos[idx][d] = centroides[c][d] + r.nextGaussian() * 0.5;
                etiquetas[idx] = c;
                idx++;
            }
        }
        return datos;
    }

    // Resultado parcial de un worker: suma de vectores por clase + conteo por clase.
    static class Parcial {
        double[][] suma;
        int[] cuenta;
        Parcial(int clases, int dim) { suma = new double[clases][dim]; cuenta = new int[clases]; }
    }

    // Entrena repartiendo el dataset entre numWorkers hilos. Devuelve los pesos
    // (un centroide por clase) y reporta el tiempo.
    public double[][] entrenarDistribuido(double[][] datos, int[] etiquetas) throws Exception {
        int total = datos.length;
        int porWorker = (int) Math.ceil(total / (double) numWorkers);

        ExecutorService pool = Executors.newFixedThreadPool(numWorkers);
        List<Future<Parcial>> futuros = new ArrayList<>();

        long t0 = System.currentTimeMillis();
        for (int w = 0; w < numWorkers; w++) {
            final int inicio = w * porWorker;
            final int fin = Math.min(inicio + porWorker, total);
            if (inicio >= fin) break;
            futuros.add(pool.submit(() -> {
                Parcial parc = new Parcial(numClases, dimension);
                for (int i = inicio; i < fin; i++) {
                    int cls = etiquetas[i];
                    parc.cuenta[cls]++;
                    for (int d = 0; d < dimension; d++) parc.suma[cls][d] += datos[i][d];
                }
                return parc;
            }));
        }

        // agrego (all-reduce) las sumas parciales de todos los workers
        double[][] sumaGlobal = new double[numClases][dimension];
        int[] cuentaGlobal = new int[numClases];
        for (Future<Parcial> f : futuros) {
            Parcial parc = f.get();
            for (int c = 0; c < numClases; c++) {
                cuentaGlobal[c] += parc.cuenta[c];
                for (int d = 0; d < dimension; d++) sumaGlobal[c][d] += parc.suma[c][d];
            }
        }
        pool.shutdown();

        double[][] pesos = new double[numClases][dimension];
        for (int c = 0; c < numClases; c++)
            for (int d = 0; d < dimension; d++)
                pesos[c][d] = cuentaGlobal[c] > 0 ? sumaGlobal[c][d] / cuentaGlobal[c] : 0;

        long ms = System.currentTimeMillis() - t0;
        System.out.println("entrenamiento distribuido: " + total + " muestras, "
                + numWorkers + " workers, " + ms + " ms");
        return pesos;
    }

    // Persiste los pesos a disco (formato de texto simple, sin librerias).
    public void guardarPesos(double[][] pesos, String ruta) throws IOException {
        try (BufferedWriter w = new BufferedWriter(new FileWriter(ruta))) {
            w.write(numClases + " " + dimension + "\n");
            for (int c = 0; c < numClases; c++) {
                StringBuilder sb = new StringBuilder();
                for (int d = 0; d < dimension; d++) {
                    if (d > 0) sb.append(" ");
                    sb.append(pesos[c][d]);
                }
                w.write(sb.toString()); w.write("\n");
            }
        }
        System.out.println("pesos guardados en " + ruta);
    }

    // Carga los pesos desde disco (para el consumo posterior).
    public static double[][] cargarPesos(String ruta) throws IOException {
        try (BufferedReader r = new BufferedReader(new FileReader(ruta))) {
            String[] cab = r.readLine().split(" ");
            int clases = Integer.parseInt(cab[0]);
            int dim = Integer.parseInt(cab[1]);
            double[][] pesos = new double[clases][dim];
            for (int c = 0; c < clases; c++) {
                String[] v = r.readLine().split(" ");
                for (int d = 0; d < dim; d++) pesos[c][d] = Double.parseDouble(v[d]);
            }
            return pesos;
        }
    }

    // Clasifica un vector: la clase cuyo centroide (peso) esta mas cerca.
    public static int clasificar(double[][] pesos, double[] x) {
        int mejor = 0;
        double menorDist = Double.MAX_VALUE;
        for (int c = 0; c < pesos.length; c++) {
            double dist = 0;
            for (int d = 0; d < x.length; d++) {
                double dif = pesos[c][d] - x[d];
                dist += dif * dif;
            }
            if (dist < menorDist) { menorDist = dist; mejor = c; }
        }
        return mejor;
    }

    // Demo: entrena, guarda, recarga y mide accuracy sobre los mismos datos.
    public static void main(String[] args) throws Exception {
        int clases = 5, dim = 8, porClase = 2000, workers = 4;
        Entrenador e = new Entrenador(clases, dim, porClase, workers);

        int[] etiquetas = new int[clases * porClase];
        double[][] datos = e.generarDatos(etiquetas);

        double[][] pesos = e.entrenarDistribuido(datos, etiquetas);
        String ruta = "pesos.txt";
        e.guardarPesos(pesos, ruta);

        double[][] recargados = cargarPesos(ruta);
        int aciertos = 0;
        for (int i = 0; i < datos.length; i++)
            if (clasificar(recargados, datos[i]) == etiquetas[i]) aciertos++;
        double acc = 100.0 * aciertos / datos.length;
        System.out.printf("accuracy con pesos recargados: %.2f%%%n", acc);
    }
}
