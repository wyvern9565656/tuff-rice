/* Renderizador do globo (CPU, inteiro) - vidro azul-claro, continentes brancos, brilho.
   Sem dependencia de Wayland: pode ser testado sozinho. */
#include "render.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MW 2048
#define MH 1024

struct Globe {
    int R, pad, w, h, N;
    uint32_t *poff;            /* indice do pixel no buffer */
    float *vx, *vy, *vz;       /* ponto na esfera, no referencial da tela */
    uint32_t *S, *L, *B;       /* camadas estaticas: mar, terra, borda (pre-multiplicadas) */
    int16_t *dcol;             /* coluna da textura relativa a lon0 */
    uint32_t *roff;            /* linha da textura * MW */
    uint16_t *tex;             /* bits 0-7 = terra, 8-15 = bordas */
    double last_lat;
    int tables_ok;
};

static float clampf(float v, float a, float b) { return v < a ? a : (v > b ? b : v); }
static float smooth(float a, float b, float x) {
    float t = clampf((x - a) / (b - a), 0.f, 1.f);
    return t * t * (3.f - 2.f * t);
}
static float mixf(float a, float b, float t) { return a + (b - a) * t; }

/* cor (0..1) + alpha (0..1) -> ARGB pre-multiplicado */
static uint32_t pack(float r, float g, float b, float a) {
    a = clampf(a, 0.f, 1.f);
    uint32_t A = (uint32_t)(a * 255.f + .5f);
    uint32_t R = (uint32_t)(clampf(r, 0.f, 1.f) * a * 255.f + .5f);
    uint32_t G = (uint32_t)(clampf(g, 0.f, 1.f) * a * 255.f + .5f);
    uint32_t B = (uint32_t)(clampf(b, 0.f, 1.f) * a * 255.f + .5f);
    return (A << 24) | (R << 16) | (G << 8) | B;
}

static uint32_t tint_pixel(uint32_t pixel, float red, float green, float blue, float opacity) {
    uint32_t alpha = pixel >> 24;
    uint32_t out_red = (pixel >> 16) & 255u;
    uint32_t out_green = (pixel >> 8) & 255u;
    uint32_t out_blue = pixel & 255u;
    alpha = (uint32_t)(alpha * opacity + 0.5f);
    out_red = (uint32_t)(out_red * red * opacity + 0.5f);
    out_green = (uint32_t)(out_green * green * opacity + 0.5f);
    out_blue = (uint32_t)(out_blue * blue * opacity + 0.5f);
    if (out_red > alpha) out_red = alpha;
    if (out_green > alpha) out_green = alpha;
    if (out_blue > alpha) out_blue = alpha;
    return (alpha << 24) | (out_red << 16) | (out_green << 8) | out_blue;
}

static inline uint32_t mix32(uint32_t a, uint32_t b, uint32_t t) { /* t: 0..255 */
    uint32_t arb = a & 0x00FF00FFu, brb = b & 0x00FF00FFu;
    uint32_t aag = (a >> 8) & 0x00FF00FFu, bag = (b >> 8) & 0x00FF00FFu;
    uint32_t rb = ((((brb - arb) * t) >> 8) + arb) & 0x00FF00FFu;
    uint32_t ag = ((((bag - aag) * t) >> 8) + aag) & 0x00FF00FFu;
    return rb | (ag << 8);
}

Globe *globe_create(int R, int pad, const char *mask_path) {
    Globe *g = calloc(1, sizeof *g);
    g->R = R; g->pad = pad;
    g->w = 2 * (R + pad);
    g->h = 2 * R + 2 * pad;

    FILE *f = fopen(mask_path, "rb");
    if (!f) { fprintf(stderr, "globo: nao abri %s\n", mask_path); free(g); return NULL; }
    uint8_t *raw = malloc(2 * MW * MH);
    if (fread(raw, 1, 2 * MW * MH, f) != (size_t)(2 * MW * MH)) {
        fprintf(stderr, "globo: mascara com tamanho errado (%s)\n", mask_path);
        fclose(f); free(raw); free(g); return NULL;
    }
    fclose(f);
    g->tex = malloc(sizeof(uint16_t) * MW * MH);
    for (int i = 0; i < MW * MH; i++) g->tex[i] = raw[i] | ((uint16_t)raw[MW * MH + i] << 8);
    free(raw);

    int maxn = g->w * g->h;
    g->poff = malloc(sizeof(uint32_t) * maxn);
    g->vx = malloc(sizeof(float) * maxn); g->vy = malloc(sizeof(float) * maxn); g->vz = malloc(sizeof(float) * maxn);
    g->S = malloc(sizeof(uint32_t) * maxn); g->L = malloc(sizeof(uint32_t) * maxn); g->B = malloc(sizeof(uint32_t) * maxn);
    g->dcol = malloc(sizeof(int16_t) * maxn); g->roff = malloc(sizeof(uint32_t) * maxn);

    float cx = (float)(R + pad);
    float cy = (float)(R + pad);
    int n = 0;
    for (int py = 0; py < g->h; py++) {
        for (int px = 0; px < g->w; px++) {
            float X = (((float)px + .5f) - cx) / R;
            float Y = (cy - ((float)py + .5f)) / R;
            float r = sqrtf(X * X + Y * Y);
            float dist = r * R;
            float cov = clampf(R + .5f - dist, 0.f, 1.f);       /* anti-serrilhado da borda */
            if (cov <= 0.f) continue;
            float Z = sqrtf(fmaxf(0.f, 1.f - r * r));
            float t = 1.f - Z;                                   /* 0 centro, 1 borda */

            /* --- vidro (mar) --- */
            float tc = powf(t, 1.5f);
            float sr = mixf(.43f, .74f, tc), sg = mixf(.78f, .92f, tc), sb = mixf(.96f, 1.0f, tc);
            float sa = mixf(.10f, .28f, powf(t, 1.6f));
            /* brilho principal (alto-esquerda) */
            float hx = X + .38f, hy = Y - .46f;
            float H = expf(-(hx * hx + hy * hy) / (2.f * .26f * .26f)) * .75f;
            sr = mixf(sr, 1.f, H); sg = mixf(sg, 1.f, H); sb = mixf(sb, 1.f, H);
            sa = sa + H * (1.f - sa) * .85f;
            /* reflexo verde-agua embaixo */
            float gx = X * .6f, gy = Y + .86f;
            float G = expf(-(gx * gx + gy * gy) / (2.f * .22f * .22f)) * .45f;
            sr = mixf(sr, .62f, G); sg = mixf(sg, 1.f, G); sb = mixf(sb, .83f, G);
            sa = sa + G * (1.f - sa) * .6f;
            /* aro de luz na borda */
            float rim = smooth(.955f, 1.f, r);
            sr = mixf(sr, 1.f, rim); sg = mixf(sg, 1.f, rim); sb = mixf(sb, 1.f, rim);
            sa = sa + rim * (1.f - sa);

            /* --- terra --- */
            float lt = powf(t, 1.2f) * .55f;
            float lr = mixf(1.f, .80f, lt), lg = mixf(1.f, .94f, lt), lb = 1.f;
            lr = mixf(lr, 1.f, H * .6f); lg = mixf(lg, 1.f, H * .6f);
            float la = mixf(.58f, .68f, t);
            la = la + rim * (1.f - la);

            g->poff[n] = (uint32_t)(py * g->w + px);
            g->vx[n] = X; g->vy[n] = Y; g->vz[n] = Z;
            g->S[n] = pack(sr, sg, sb, sa * cov);
            g->L[n] = pack(lr, lg, lb, la * cov);
            g->B[n] = pack(.36f, .66f, .90f, .95f * cov);
            n++;
        }
    }
    g->N = n;
    g->last_lat = 1e9;
    return g;
}

void globe_size(const Globe *g, int *w, int *h) { *w = g->w; *h = g->h; }

static void build_tables(Globe *g, double lat0) {
    float c = (float)cos(lat0), s = (float)sin(lat0);
    const float inv_pi = 1.f / (float)M_PI, inv_2pi = 1.f / (2.f * (float)M_PI);
    for (int i = 0; i < g->N; i++) {
        float Yp = g->vy[i] * c + g->vz[i] * s;
        float Zp = g->vz[i] * c - g->vy[i] * s;
        float lat = asinf(clampf(Yp, -1.f, 1.f));
        int row = (int)((0.5f - lat * inv_pi) * MH);
        if (row < 0) row = 0;
        if (row > MH - 1) row = MH - 1;
        float dl = atan2f(g->vx[i], Zp);
        g->dcol[i] = (int16_t)lrintf(dl * inv_2pi * MW);
        g->roff[i] = (uint32_t)row * MW;
    }
    g->last_lat = lat0;
    g->tables_ok = 1;
}

void globe_render(Globe *g, uint32_t *buf, int stride, double lon0, double lat0,
                  uint32_t color_rgb, uint32_t land_color_rgb, float opacity) {
    if (!g->tables_ok || fabs(lat0 - g->last_lat) > 0.0015) build_tables(g, lat0);
    int lonidx = (int)floor(lon0 / (2.0 * M_PI) * MW) + MW / 2;
    if (opacity < 0.0f) opacity = 0.0f;
    if (opacity > 1.0f) opacity = 1.0f;
    float red = ((color_rgb >> 16) & 255u) / 255.0f;
    float green = ((color_rgb >> 8) & 255u) / 255.0f;
    float blue = (color_rgb & 255u) / 255.0f;
    float land_red = ((land_color_rgb >> 16) & 255u) / 255.0f;
    float land_green = ((land_color_rgb >> 8) & 255u) / 255.0f;
    float land_blue = (land_color_rgb & 255u) / 255.0f;
    for (int i = 0; i < g->N; i++) {
        uint16_t tx = g->tex[g->roff[i] + (uint32_t)((g->dcol[i] + lonidx) & (MW - 1))];
        uint32_t m = tx & 255u, b = tx >> 8;
        uint32_t sea = tint_pixel(g->S[i], red / 0.56f,
                                  green / 0.85f, blue / 0.98f, opacity);
        uint32_t land = tint_pixel(g->L[i], land_red, land_green, land_blue, opacity);
        uint32_t border = pack(red, green, blue, 0.95f * opacity);
        uint32_t px = m == 0 ? sea : (m == 255u ? land : mix32(sea, land, m));
        if (b) px = mix32(px, border, (b * 100u) >> 8);
        uint32_t source = g->poff[i];
        size_t target = (size_t)(source / g->w) * stride + source % g->w;
        buf[target] = px;
    }
}
