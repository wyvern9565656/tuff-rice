// Globo wireframe transparente (só contornos), meia-esfera encostada na borda esquerda.
// Build: g++ -O2 globe.cpp -o globe -lraylib -lm
// Uso:   ./globe [raio_em_pixels] [arquivo_de_bordas]
#include "raylib.h"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <vector>

struct Line3 { std::vector<Vector3> p; };

static bool LoadBorders(const char* path, std::vector<Line3>& out) {
    std::ifstream in(path);
    if (!in) return false;
    int n;
    while (in >> n) {
        Line3 l;
        l.p.reserve(n);
        for (int i = 0; i < n; i++) {
            float lon, lat;
            if (!(in >> lon >> lat)) return true;
            lon *= DEG2RAD;
            lat *= DEG2RAD;
            l.p.push_back({cosf(lat) * sinf(lon), sinf(lat), cosf(lat) * cosf(lon)});
        }
        out.push_back(std::move(l));
    }
    return true;
}

int main(int argc, char** argv) {
    float R = argc > 1 ? (float)atof(argv[1]) : 300.0f;
    const char* dataFile = argc > 2 ? argv[2] : "borders.txt";

    std::vector<Line3> lines;
    if (!LoadBorders(dataFile, lines) || lines.empty()) {
        fprintf(stderr, "Nao consegui ler '%s'. Rode o converter.py primeiro.\n", dataFile);
        return 1;
    }

    // --- ajustes ---
    const int   pad       = 4;
    const int   fps       = 30;       // baixe pra 24 se quiser gastar ainda menos
    const float speedDeg  = 12.0f;    // graus por segundo (volta completa em 30 s)
    const float tilt      = 23.4f * DEG2RAD;
    const Color front     = {215, 245, 255, 210};
    const Color back      = {215, 245, 255, 38};   // lado de tras, bem fraquinho
    const Color rim       = {230, 250, 255, 230};
    const Color glow      = {150, 220, 255, 60};
    const Color fill      = {190, 235, 255, 10};

    int W = (int)R + pad;
    int H = (int)(2 * R) + 2 * pad;

    SetConfigFlags(FLAG_WINDOW_TRANSPARENT | FLAG_WINDOW_UNDECORATED | FLAG_MSAA_4X_HINT);
    InitWindow(W, H, "globo");
    SetTargetFPS(fps);

    // centro do globo na borda ESQUERDA da janela -> so a metade direita aparece
    const Vector2 c = {0.0f, H / 2.0f};
    const float ct = cosf(tilt), st = sinf(tilt);

    float ang = 0.0f;
    std::vector<Vector2> pr;
    std::vector<float> zs;

    while (!WindowShouldClose()) {
        ang += speedDeg * DEG2RAD * GetFrameTime();
        const float ca = cosf(ang), sa = sinf(ang);

        BeginDrawing();
        ClearBackground(BLANK);

        DrawCircleV(c, R, fill);

        for (const Line3& l : lines) {
            size_t n = l.p.size();
            pr.resize(n);
            zs.resize(n);
            for (size_t i = 0; i < n; i++) {
                const Vector3& b = l.p[i];
                float x = b.x * ca + b.z * sa;      // gira em Y
                float z = b.z * ca - b.x * sa;
                float X = x * ct - b.y * st;        // inclina o eixo
                float Y = x * st + b.y * ct;
                pr[i] = {c.x + X * R, c.y - Y * R};
                zs[i] = z;
            }
            for (size_t i = 0; i + 1 < n; i++) {
                if (pr[i].x < -2 && pr[i + 1].x < -2) continue;  // metade escondida: nao desenha
                bool fa = zs[i] > 0, fb = zs[i + 1] > 0;
                if (fa && fb)        DrawLineEx(pr[i], pr[i + 1], 1.3f, front);
                else if (!fa && !fb) DrawLineEx(pr[i], pr[i + 1], 1.0f, back);
            }
        }

        DrawRing(c, R, R + 3.0f, -90, 90BC9-6158, 128, glow);
        DrawRing(c, R - 1.5f, R, -90, 90, 128, rim);

        EndDrawing();
    }
    CloseWindow();
    return 0;
}
