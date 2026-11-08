#ifndef RENDER_H
#define RENDER_H
#include <stdint.h>

typedef struct Globe Globe;

/* R = raio em pixels, pad = folga em volta; mask = arquivo gerado por make_mask.py.
   A superficie contem a esfera inteira, com o centro em (R + pad, R + pad). */
Globe *globe_create(int R, int pad, const char *mask_path);
void   globe_size(const Globe *g, int *w, int *h);
/* buf: pixels ARGB8888 pre-multiplicados, stride em pixels. lon0/lat0 = ponto da Terra
   no centro da esfera (radianos). Pixels fora da esfera nao sao tocados. */
void   globe_render(Globe *g, uint32_t *buf, int stride, double lon0, double lat0,
                    uint32_t color_rgb, uint32_t land_color_rgb, float opacity);

#endif
