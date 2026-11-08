/* globo-layer: globo de vidro interativo como superficie layer-shell (camada BOTTOM).
   Fica atras das janelas, recebe clique/arrasto do mouse quando esta visivel. */
#define _GNU_SOURCE
#include <errno.h>
#include <math.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

#include <cairo.h>
#include <wayland-client.h>
#include "wlr-layer-shell-unstable-v1-client-protocol.h"

#include "render.h"

#define BTN_LEFT 0x110
#define BTN_RIGHT 0x111
#define OUTSIDE_Y 72

struct buf { struct wl_buffer *wl; uint32_t *data; int busy; };

static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct wl_seat *seat;
static struct wl_pointer *pointer;
static struct wl_output *output;
static struct zwlr_layer_shell_v1 *layer_shell;
static struct wl_surface *surface;
static struct zwlr_layer_surface_v1 *layer_surface;
static int configured = 0, running = 1;

static struct buf bufs[2];
static Globe *globe;
static int W, H, R, PAD;
static int outside_x = 144;
static int globe_cx, globe_cy;
static int screen_w = 1368, screen_h = 768;
static int surface_x, surface_y;
static double dock_cx, dock_cy;
static volatile sig_atomic_t settings_changed = 0;
static int settings_render_pending = 0;
static char settings_path[512];
static struct stat settings_snapshot;
static int settings_snapshot_ready = 0;
static float globe_opacity = 1.0f;
static uint32_t globe_color_rgb = 0x62b9e8;
static uint32_t globe_land_color_rgb = 0xffffff;
static int hypr_events = -1;
static int open_windows = 0;
static char event_buffer[8192];
static size_t event_used = 0;

/* estado da animacao / mouse */
static double lon0 = -1.05, lat0 = 0.35;   /* centro da vista (radianos) */
static const double LAT_HOME = 0.35;
static double vlon = 0.0;                  /* velocidade de giro (rad/s) */
static double spin = 0.21;                 /* giro automatico: ~12 graus/s */
static int rotate_dragging = 0;
static int move_dragging = 0;
static int docked = 1;
static int anim_target_docked = 0;
static double last_x, last_y;
static double drag_start_x, drag_start_y, drag_start_pointer_x, drag_start_pointer_y;
static double drag_target_x, drag_target_y, drag_progress = 0.0, last_t;
static double drag_reveal_distance = 0.0;
static double drag_vlon = 0.0;
static int animating = 0;
static double anim_start, anim_duration = 2.4;
static double anim_center_x, anim_center_y, anim_target_x, anim_target_y, anim_lon, anim_lat;
static double anim_v0, anim_v1;

struct Country {
    char name[96];
    char continent[32];
    char timezone[64]; // Added timezone field
    char local_time[8]; // Added local_time field
    unsigned long long population;
    double lat, lon;
};

#define MAX_COUNTRIES 256
static struct Country countries[MAX_COUNTRIES];
static size_t country_count;
static time_t country_times_updated;

static void set_circle_input_region(int half_only);

static double now(void) {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec / 1e9;
}

static double wrap_angle(double angle) {
    return remainder(angle, 2.0 * M_PI);
}

static int compare_countries(const void *left, const void *right) {
    const struct Country *a = left;
    const struct Country *b = right;
    int continent_order = strcmp(a->continent, b->continent);
    return continent_order ? continent_order : strcmp(a->name, b->name);
}

static void load_country_data(const char *path) {
    FILE *file = fopen(path, "r");
    if (!file) {
        fprintf(stderr, "globo: nao abri os dados dos paises %s\n", path);
        return;
    }

    char line[256];
    while (country_count < MAX_COUNTRIES && fgets(line, sizeof line, file)) {
        char *name = strtok(line, "\t\r\n");
        char *continent = strtok(NULL, "\t\r\n");
        char *population = strtok(NULL, "\t\r\n");
        char *latitude = strtok(NULL, "\t\r\n");
        char *longitude = strtok(NULL, "\t\r\n");
        char *timezone = strtok(NULL, "\t\r\n");
        if (!name || !continent || !population || !latitude || !longitude) continue;

        struct Country *country = &countries[country_count++];
        snprintf(country->name, sizeof country->name, "%s", name);
        snprintf(country->continent, sizeof country->continent, "%s", continent);
        snprintf(country->timezone, sizeof country->timezone, "%s",
             timezone ? timezone : "Etc/UTC");
        snprintf(country->local_time, sizeof country->local_time, "--:--");
        country->population = strtoull(population, NULL, 10);
        country->lat = strtod(latitude, NULL);
        country->lon = strtod(longitude, NULL);
    }
    fclose(file);
    qsort(countries, country_count, sizeof countries[0], compare_countries);
}

static void update_country_times(void) {
    time_t current = time(NULL);
    if (country_times_updated && current >= country_times_updated &&
        current - country_times_updated < 30) return;

    const char *old_tz = getenv("TZ");
    char *saved_tz = old_tz ? strdup(old_tz) : NULL;
    if (old_tz && !saved_tz) return;

    for (size_t i = 0; i < country_count; i++) {
        struct tm local_time;
        if (!countries[i].timezone[0] || setenv("TZ", countries[i].timezone, 1) != 0) {
            snprintf(countries[i].local_time, sizeof countries[i].local_time, "--:--");
            continue;
        }
        tzset();
        if (localtime_r(&current, &local_time))
            strftime(countries[i].local_time, sizeof countries[i].local_time,
                     "%H:%M", &local_time);
        else
            snprintf(countries[i].local_time, sizeof countries[i].local_time, "--:--");
    }

    if (saved_tz) {
        setenv("TZ", saved_tz, 1);
        free(saved_tz);
    } else {
        unsetenv("TZ");
    }
    tzset();
    country_times_updated = current;
}

static void set_surface_position(double cx, double cy) {
    int x = (int)lrint(cx - globe_cx);
    int y = (int)lrint(cy - globe_cy);
    if (x == surface_x && y == surface_y) return;
    surface_x = x;
    surface_y = y;
    zwlr_layer_surface_v1_set_margin(layer_surface, surface_y, 0, 0, surface_x);
    wl_surface_commit(surface);
}

static double fully_visible_progress(double start_x, double start_y,
                                     double delta_x, double delta_y, double distance) {
    double edge = R + PAD;
    double left = fmax(edge, dock_cx + R);
    double right = screen_w - edge;
    double bottom = screen_h - edge;
    if (right < left || bottom < edge) return distance;

    double fraction = 0.0;
    if (start_x < left && delta_x > 0.0)
        fraction = fmax(fraction, (left - start_x) / delta_x);
    else if (start_x > right && delta_x < 0.0)
        fraction = fmax(fraction, (right - start_x) / delta_x);
    if (start_y < edge && delta_y > 0.0)
        fraction = fmax(fraction, (edge - start_y) / delta_y);
    else if (start_y > bottom && delta_y < 0.0)
        fraction = fmax(fraction, (bottom - start_y) / delta_y);

    return distance * fmin(1.0, fmax(0.0, fraction));
}

static void start_return_animation(double target_x, double target_y, int target_is_docked) {
    animating = 1;
    anim_start = now();
    anim_center_x = globe_cx + surface_x;
    anim_center_y = globe_cy + surface_y;
    anim_target_x = target_x;
    anim_target_y = target_y;
    anim_target_docked = target_is_docked;
    anim_lon = lon0;
    anim_lat = lat0;
    anim_v0 = fabs(drag_vlon) > 0.8 ? drag_vlon : -12.0;
    if (anim_v0 > 14.0) anim_v0 = 14.0;
    if (anim_v0 < -14.0) anim_v0 = -14.0;
    anim_v1 = -spin;
}

static int count_windows(void) {
    const char *command =
        "python3 -c 'import json,subprocess; "
        "workspace=json.loads(subprocess.check_output([\"hyprctl\",\"activeworkspace\",\"-j\"],text=True))[\"id\"]; "
        "clients=json.loads(subprocess.check_output([\"hyprctl\",\"clients\",\"-j\"],text=True)); "
        "print(sum(client.get(\"workspace\",{}).get(\"id\")==workspace for client in clients))'";
    FILE *p = popen(command, "r");
    if (!p) return 0;
    char result[32] = {0};
    fgets(result, sizeof result, p);
    pclose(p);
    return atoi(result);
}

static int connect_hypr_events(void) {
    const char *runtime = getenv("XDG_RUNTIME_DIR");
    const char *signature = getenv("HYPRLAND_INSTANCE_SIGNATURE");
    if (!runtime || !signature) return -1;

    char path[sizeof(((struct sockaddr_un *)0)->sun_path)];
    int length = snprintf(path, sizeof path, "%s/hypr/%s/.socket2.sock", runtime, signature);
    if (length < 0 || (size_t)length >= sizeof path) return -1;

    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) return -1;
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    snprintf(address.sun_path, sizeof address.sun_path, "%s", path);
    if (connect(fd, (struct sockaddr *)&address, sizeof address) < 0) {
        close(fd);
        return -1;
    }
    int flags = fcntl(fd, F_GETFL, 0);
    if (flags >= 0) fcntl(fd, F_SETFL, flags | O_NONBLOCK);
    return fd;
}

static void handle_hypr_events(void) {
    char incoming[2048];
    ssize_t count = read(hypr_events, incoming, sizeof incoming);
    if (count <= 0) return;
    for (ssize_t i = 0; i < count; i++) {
        char ch = incoming[i];
        if (ch != '\n' && event_used + 1 < sizeof event_buffer) {
            event_buffer[event_used++] = ch;
            continue;
        }
        event_buffer[event_used] = '\0';
        if (strncmp(event_buffer, "openwindow>>", 12) == 0 ||
            strncmp(event_buffer, "closewindow>>", 13) == 0 ||
            strncmp(event_buffer, "workspace>>", 11) == 0 ||
            strncmp(event_buffer, "focusedmon>>", 12) == 0)
            open_windows = count_windows();
        event_used = 0;
    }
}

/* ---------------- ponteiro ---------------- */
static void p_enter(void *d, struct wl_pointer *p, uint32_t s, struct wl_surface *sf, wl_fixed_t x, wl_fixed_t y) {
    (void)d;(void)p;(void)s;(void)sf;
    last_x = wl_fixed_to_double(x);
    last_y = wl_fixed_to_double(y);
}
static void p_leave(void *d, struct wl_pointer *p, uint32_t s, struct wl_surface *sf) {
    (void)d;(void)p;(void)s;(void)sf;
    /* A drag keeps pointer focus because the globe follows the cursor. */
}
static void p_motion(void *d, struct wl_pointer *p, uint32_t t, wl_fixed_t fx, wl_fixed_t fy) {
    (void)d;(void)p;(void)t;
    double x = wl_fixed_to_double(fx), y = wl_fixed_to_double(fy);
    if (rotate_dragging) {
        double dx = x - last_x, dy = y - last_y, tn = now(), dt = tn - last_t;
        lon0 = wrap_angle(lon0 - dx / R);
        lat0 = wrap_angle(lat0 + dy / R);
        if (dt > 1e-3) drag_vlon = 0.6 * drag_vlon + 0.4 * (-dx / R / dt);
        last_t = tn;
    }
    if (move_dragging) {
        double global_x = surface_x + x, global_y = surface_y + y;
        double dx = global_x - drag_start_pointer_x;
        double dy = global_y - drag_start_pointer_y;
        if (docked) {
            double distance = hypot(drag_target_x - drag_start_x, drag_target_y - drag_start_y);
            if (distance > 0.0) {
                double requested = dx * (drag_target_x - drag_start_x) +
                                   dy * (drag_target_y - drag_start_y);
                double progress = fmin(drag_reveal_distance, fmax(0.0, requested / distance));
                drag_progress = progress;
                double ux = (drag_target_x - drag_start_x) / distance;
                double uy = (drag_target_y - drag_start_y) / distance;
                set_surface_position(drag_start_x + ux * progress, drag_start_y + uy * progress);
            }
        } else {
            double edge = R + PAD;
            double center_x = drag_start_x + dx;
            double center_y = drag_start_y + dy;
            center_x = fmin(screen_w - edge, fmax(edge, center_x));
            center_y = fmin(screen_h - edge, fmax(edge, center_y));
            set_surface_position(center_x, center_y);
        }
    }
    last_x = x; last_y = y;
}
static void p_button(void *d, struct wl_pointer *p, uint32_t s, uint32_t t, uint32_t button, uint32_t state) {
    (void)d;(void)p;(void)s;(void)t;
    if (button != BTN_LEFT && button != BTN_RIGHT) return;
    double local_cx = globe_cx, local_cy = globe_cy;
    double hit_x = last_x - local_cx, hit_y = last_y - local_cy;
    if (state == WL_POINTER_BUTTON_STATE_PRESSED) {
        if (hit_x * hit_x + hit_y * hit_y > (double)(R + 6) * (R + 6)) return;
        if (button == BTN_LEFT) {
            animating = 0;
            rotate_dragging = 1;
            drag_vlon = 0;
            last_t = now();
        } else {
            animating = 0;
            move_dragging = 1;
            set_circle_input_region(0);
            drag_progress = 0.0;
            drag_start_x = local_cx + surface_x;
            drag_start_y = local_cy + surface_y;
            drag_start_pointer_x = surface_x + last_x;
            drag_start_pointer_y = surface_y + last_y;
            drag_target_x = screen_w * 0.5;
            drag_target_y = screen_h * 0.5;
            double reveal_start_x = docked ? drag_start_x : dock_cx;
            double reveal_start_y = docked ? drag_start_y : dock_cy;
            double delta_x = drag_target_x - reveal_start_x;
            double delta_y = drag_target_y - reveal_start_y;
            double distance = hypot(delta_x, delta_y);
            drag_reveal_distance = fully_visible_progress(
                reveal_start_x, reveal_start_y, delta_x, delta_y, distance);
        }
    } else {
        if (button == BTN_LEFT && rotate_dragging) {
            vlon = drag_vlon;
            if (vlon > 6) vlon = 6;
            if (vlon < -6) vlon = -6;
            rotate_dragging = 0;
        } else if (button == BTN_RIGHT && move_dragging) {
            if (docked && drag_progress >= drag_reveal_distance - 1.0) {
                start_return_animation(screen_w * 0.5, screen_h * 0.5, 0);
            } else if (docked) {
                start_return_animation(dock_cx, dock_cy, 1);
            } else {
                double center_x = R + PAD + surface_x;
                double center_y = R + PAD + surface_y;
                int return_to_dock = hypot(center_x - dock_cx, center_y - dock_cy) <= R * 0.85;
                start_return_animation(return_to_dock ? dock_cx : screen_w * 0.5,
                                       return_to_dock ? dock_cy : screen_h * 0.5,
                                       return_to_dock);
            }
            move_dragging = 0;
        }
    }
}
static void p_axis(void *d, struct wl_pointer *p, uint32_t t, uint32_t a, wl_fixed_t v) {
    (void)d;(void)p;(void)t;(void)a;
    lon0 = wrap_angle(lon0 + wl_fixed_to_double(v) * 0.004); /* rolar a roda tambem gira */
}
static const struct wl_pointer_listener pointer_listener = {
    .enter = p_enter, .leave = p_leave, .motion = p_motion, .button = p_button, .axis = p_axis,
};

static void seat_caps(void *d, struct wl_seat *s, uint32_t caps) {
    (void)d;
    if ((caps & WL_SEAT_CAPABILITY_POINTER) && !pointer) {
        pointer = wl_seat_get_pointer(s);
        wl_pointer_add_listener(pointer, &pointer_listener, NULL);
    }
}
static void seat_name(void *d, struct wl_seat *s, const char *n) { (void)d;(void)s;(void)n; }
static const struct wl_seat_listener seat_listener = { .capabilities = seat_caps, .name = seat_name };

static void output_geometry(void *d, struct wl_output *o, int32_t x, int32_t y,
                            int32_t physical_width, int32_t physical_height,
                            int32_t subpixel, const char *make, const char *model,
                            int32_t transform) {
    (void)d;(void)o;(void)x;(void)y;(void)physical_width;(void)physical_height;
    (void)subpixel;(void)make;(void)model;(void)transform;
}
static void output_mode(void *d, struct wl_output *o, uint32_t flags, int32_t width, int32_t height, int32_t refresh) {
    (void)d;(void)o;(void)refresh;
    if (flags & WL_OUTPUT_MODE_CURRENT) {
        screen_w = width;
        screen_h = height;
    }
}
static const struct wl_output_listener output_listener = {
    .geometry = output_geometry,
    .mode = output_mode,
};

/* ---------------- layer surface ---------------- */
static void ls_configure(void *d, struct zwlr_layer_surface_v1 *ls, uint32_t serial, uint32_t w, uint32_t h) {
    (void)d;(void)w;(void)h;
    zwlr_layer_surface_v1_ack_configure(ls, serial);
    configured = 1;
}
static void ls_closed(void *d, struct zwlr_layer_surface_v1 *ls) { (void)d;(void)ls; running = 0; }
static const struct zwlr_layer_surface_v1_listener ls_listener = { .configure = ls_configure, .closed = ls_closed };

/* ---------------- registro ---------------- */
static void reg_global(void *d, struct wl_registry *r, uint32_t name, const char *iface, uint32_t ver) {
    (void)d;
    if (!strcmp(iface, wl_compositor_interface.name))
        compositor = wl_registry_bind(r, name, &wl_compositor_interface, ver < 4 ? ver : 4);
    else if (!strcmp(iface, wl_shm_interface.name))
        shm = wl_registry_bind(r, name, &wl_shm_interface, 1);
    else if (!strcmp(iface, wl_seat_interface.name)) {
        seat = wl_registry_bind(r, name, &wl_seat_interface, ver < 4 ? ver : 4);
        wl_seat_add_listener(seat, &seat_listener, NULL);
    } else if (!strcmp(iface, wl_output_interface.name) && !output) {
        output = wl_registry_bind(r, name, &wl_output_interface, 1);
        wl_output_add_listener(output, &output_listener, NULL);
    } else if (!strcmp(iface, zwlr_layer_shell_v1_interface.name))
        layer_shell = wl_registry_bind(r, name, &zwlr_layer_shell_v1_interface, ver < 4 ? ver : 4);
}
static void reg_remove(void *d, struct wl_registry *r, uint32_t n) { (void)d;(void)r;(void)n; }
static const struct wl_registry_listener reg_listener = { .global = reg_global, .global_remove = reg_remove };

/* ---------------- buffers ---------------- */
static void buf_release(void *d, struct wl_buffer *b) { (void)b; ((struct buf *)d)->busy = 0; }
static const struct wl_buffer_listener buf_listener = { .release = buf_release };

static int create_buffers(void) {
    size_t stride = (size_t)W * 4, one = stride * H, total = one * 2;
    int fd = memfd_create("globo-layer", MFD_CLOEXEC);
    if (fd < 0 || ftruncate(fd, (off_t)total) < 0) { perror("memfd"); return -1; }
    uint8_t *map = mmap(NULL, total, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) { perror("mmap"); return -1; }
    struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, (int32_t)total);
    for (int i = 0; i < 2; i++) {
        bufs[i].wl = wl_shm_pool_create_buffer(pool, (int32_t)(one * i), W, H, (int32_t)stride, WL_SHM_FORMAT_ARGB8888);
        bufs[i].data = (uint32_t *)(map + one * i);
        bufs[i].busy = 0;
        wl_buffer_add_listener(bufs[i].wl, &buf_listener, &bufs[i]);
    }
    wl_shm_pool_destroy(pool);
    close(fd);
    return 0;
}

static void set_circle_input_region(int half_only) {
    struct wl_region *region = wl_compositor_create_region(compositor);
    for (int y = 0; y < H; y++) {
        double dy = y + 0.5 - globe_cy;
        double remain = (double)R * R - dy * dy;
        if (remain <= 0.0) continue;
        int half_width = (int)floor(sqrt(remain));
        if (half_only)
            wl_region_add(region, globe_cx, y, half_width + 1, 1);
        else
            wl_region_add(region, globe_cx - half_width, y, half_width * 2 + 1, 1);
    }
    wl_surface_set_input_region(surface, region);
    wl_region_destroy(region);
    wl_surface_commit(surface);
}

struct CountryPoint { double x, y, depth; };
struct LabelRect { double x, y, w, h; };

static int globe_is_centered(void) {
    if (docked || animating || move_dragging) return 0;
    double center_x = surface_x + globe_cx;
    double center_y = surface_y + globe_cy;
    return fabs(center_x - screen_w * 0.5) <= 1.0 &&
           fabs(center_y - screen_h * 0.5) <= 1.0;
}

static const char *continent_name(const char *continent) {
    if (strcmp(continent, "Africa") == 0) return "Africa";
    if (strcmp(continent, "Asia") == 0) return "Asia";
    if (strcmp(continent, "Europe") == 0) return "Europa";
    if (strcmp(continent, "North America") == 0) return "America do Norte";
    if (strcmp(continent, "South America") == 0) return "America do Sul";
    if (strcmp(continent, "Oceania") == 0) return "Oceania";
    if (strcmp(continent, "Antarctica") == 0) return "Antartida";
    if (strcmp(continent, "Seven seas") == 0) return "Oceanos";
    return continent;
}

static void project_country(size_t index, struct CountryPoint *point) {
    double lat = countries[index].lat * M_PI / 180.0;
    double lon = countries[index].lon * M_PI / 180.0;
    double delta_lon = lon - lon0;
    double x = cos(lat) * sin(delta_lon);
    double z_rotated = cos(lat) * cos(delta_lon);
    double y_rotated = sin(lat);
    double cos_lat0 = cos(lat0), sin_lat0 = sin(lat0);
    double y = y_rotated * cos_lat0 - z_rotated * sin_lat0;

    point->x = globe_cx + x * R;
    point->y = globe_cy - y * R;
    point->depth = y_rotated * sin_lat0 + z_rotated * cos_lat0;
}

static void rounded_rectangle(cairo_t *cr, double x, double y, double w,
                              double h, double radius) {
    cairo_new_sub_path(cr);
    cairo_arc(cr, x + w - radius, y + radius, radius, -M_PI_2, 0);
    cairo_arc(cr, x + w - radius, y + h - radius, radius, 0, M_PI_2);
    cairo_arc(cr, x + radius, y + h - radius, radius, M_PI_2, M_PI);
    cairo_arc(cr, x + radius, y + radius, radius, M_PI, 3 * M_PI_2);
    cairo_close_path(cr);
}

static void show_fitted_text(cairo_t *cr, const char *text, double x,
                             double baseline, double max_width, double font_size) {
    cairo_text_extents_t extents;
    for (;;) {
        cairo_set_font_size(cr, font_size);
        cairo_text_extents(cr, text, &extents);
        if (extents.x_advance <= max_width || font_size <= 6.0) break;
        font_size -= 0.5;
    }
    cairo_move_to(cr, x, baseline);
    cairo_show_text(cr, text);
}

static void set_continent_color(cairo_t *cr, const char *continent, double alpha) {
    if (strcmp(continent, "Africa") == 0)
        cairo_set_source_rgba(cr, 0.98, 0.65, 0.38, alpha);
    else if (strcmp(continent, "Antarctica") == 0)
        cairo_set_source_rgba(cr, 0.76, 0.88, 1.00, alpha);
    else if (strcmp(continent, "Asia") == 0)
        cairo_set_source_rgba(cr, 0.35, 0.78, 1.00, alpha);
    else if (strcmp(continent, "Europe") == 0)
        cairo_set_source_rgba(cr, 0.48, 0.90, 0.66, alpha);
    else if (strcmp(continent, "North America") == 0)
        cairo_set_source_rgba(cr, 0.62, 0.70, 1.00, alpha);
    else if (strcmp(continent, "Oceania") == 0)
        cairo_set_source_rgba(cr, 0.38, 0.88, 0.82, alpha);
    else if (strcmp(continent, "South America") == 0)
        cairo_set_source_rgba(cr, 1.00, 0.72, 0.42, alpha);
    else
        cairo_set_source_rgba(cr, 0.76, 0.80, 0.84, alpha);
}

static void render_country_atlas(uint32_t *pixels) {
    static double previous_bubble_x[MAX_COUNTRIES];
    static double previous_bubble_y[MAX_COUNTRIES];
    static int previous_bubble_valid[MAX_COUNTRIES];
    struct Bubble {
        int country;
        double x, y, width, height, font_size;
    } bubbles[MAX_COUNTRIES];
    struct CountryPoint points[MAX_COUNTRIES];
    int visible[MAX_COUNTRIES];
    size_t visible_count = 0;
    int front_country = -1;
    double front_depth = 0.0;

    for (size_t i = 0; i < country_count; i++) {
        project_country(i, &points[i]);
        if (points[i].depth > 0.0) visible[visible_count++] = (int)i;
        if (points[i].depth > front_depth) {
            front_depth = points[i].depth;
            front_country = (int)i;
        }
    }

    for (size_t i = 1; i < visible_count; i++) {
        int index = visible[i];
        size_t position = i;
        while (position > 0 && points[visible[position - 1]].depth < points[index].depth) {
            visible[position] = visible[position - 1];
            position--;
        }
        visible[position] = index;
    }

    cairo_surface_t *surface = cairo_image_surface_create_for_data(
        (unsigned char *)pixels, CAIRO_FORMAT_ARGB32, W, H, W * 4);
    if (cairo_surface_status(surface) != CAIRO_STATUS_SUCCESS) {
        cairo_surface_destroy(surface);
        return;
    }
    cairo_surface_mark_dirty(surface);
    cairo_t *cr = cairo_create(surface);
    cairo_select_font_face(cr, "Sans", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_NORMAL);

    static const double directions[8][2] = {
        {1.0, 0.0}, {-1.0, 0.0}, {0.0, -1.0}, {0.0, 1.0},
        {0.707, -0.707}, {-0.707, -0.707}, {0.707, 0.707}, {-0.707, 0.707},
    };
    static const double distances[] = {8.0, 20.0, 32.0, 44.0, 56.0, 68.0};
    size_t placed_count = 0;
    double default_font = visible_count > 110 ? 7.2 : (visible_count > 65 ? 8.0 : 9.0);

    for (size_t visible_index = 0; visible_index < visible_count; visible_index++) {
        int index = visible[visible_index];
        char detail[64] = "";
        double font_size = default_font;
        cairo_text_extents_t name_extents, detail_extents;
        cairo_set_font_size(cr, font_size);
        cairo_text_extents(cr, countries[index].name, &name_extents);
        while (name_extents.x_advance > 210.0 && font_size > 6.0) {
            font_size -= 0.5;
            cairo_set_font_size(cr, font_size);
            cairo_text_extents(cr, countries[index].name, &name_extents);
        }

        double width = name_extents.x_advance + 10.0;
        double height = font_size + 6.0;
        if (index == front_country) {
            snprintf(detail, sizeof detail, "%s - %s",
                     continent_name(countries[index].continent), countries[index].local_time);
            cairo_set_font_size(cr, 6.2);
            cairo_text_extents(cr, detail, &detail_extents);
            width = fmax(width, detail_extents.x_advance + 10.0);
            height += 8.0;
        }
        if (width > W - 12.0) width = W - 12.0;

        double best_score = HUGE_VAL;
        struct Bubble best = {.country = index, .width = width,
                              .height = height, .font_size = font_size};
        for (size_t ring = 0; ring < sizeof distances / sizeof distances[0]; ring++) {
            for (int direction = 0; direction < 8; direction++) {
                double dx = directions[direction][0] * distances[ring];
                double dy = directions[direction][1] * distances[ring];
                double x = points[index].x + dx;
                if (dx < -0.1) x -= width;
                else if (fabs(dx) <= 0.1) x -= width * 0.5;
                double y = points[index].y + dy - height * 0.5;
                x = fmax(6.0, fmin(W - width - 6.0, x));
                y = fmax(6.0, fmin(H - height - 6.0, y));

                double target_x = fmax(x, fmin(points[index].x, x + width));
                double target_y = fmax(y, fmin(points[index].y, y + height));
                double tether = hypot(target_x - points[index].x,
                                      target_y - points[index].y);
                double movement = previous_bubble_valid[index]
                    ? hypot(x - previous_bubble_x[index], y - previous_bubble_y[index])
                    : 0.0;
                double overlap = 0.0;
                for (size_t other = 0; other < placed_count; other++) {
                    double overlap_x = fmin(x + width + 2.0,
                        bubbles[other].x + bubbles[other].width + 2.0) -
                        fmax(x - 2.0, bubbles[other].x - 2.0);
                    double overlap_y = fmin(y + height + 2.0,
                        bubbles[other].y + bubbles[other].height + 2.0) -
                        fmax(y - 2.0, bubbles[other].y - 2.0);
                    if (overlap_x > 0.0 && overlap_y > 0.0)
                        overlap += overlap_x * overlap_y;
                }
                double score = tether + movement * 0.25 + overlap * 1000.0;
                if (score < best_score) {
                    best_score = score;
                    best.x = x;
                    best.y = y;
                }
            }
        }
        bubbles[placed_count++] = best;
        previous_bubble_x[index] = best.x;
        previous_bubble_y[index] = best.y;
        previous_bubble_valid[index] = 1;
    }

    cairo_set_line_width(cr, 0.8);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_ROUND);
    for (size_t i = 0; i < placed_count; i++) {
        int index = bubbles[i].country;
        double target_x = fmax(bubbles[i].x,
            fmin(points[index].x, bubbles[i].x + bubbles[i].width));
        double target_y = fmax(bubbles[i].y,
            fmin(points[index].y, bubbles[i].y + bubbles[i].height));
        if (hypot(target_x - points[index].x, target_y - points[index].y) < 2.0) continue;
        set_continent_color(cr, countries[index].continent,
                            index == front_country ? 0.72 : 0.50);
        cairo_move_to(cr, points[index].x, points[index].y);
        cairo_line_to(cr, target_x, target_y);
        cairo_stroke(cr);
    }

    for (size_t i = 0; i < visible_count; i++) {
        int index = visible[i];
        double depth = fmin(points[index].depth, 1.0);
        double radius = index == front_country ? 5.0 : 2.2 + depth * 0.8;
        cairo_arc(cr, points[index].x, points[index].y, radius + 1.5, 0, 2 * M_PI);
        set_continent_color(cr, countries[index].continent,
                            index == front_country ? 0.48 : 0.24);
        cairo_fill(cr);
        cairo_arc(cr, points[index].x, points[index].y, radius, 0, 2 * M_PI);
        set_continent_color(cr, countries[index].continent,
                            index == front_country ? 1.0 : 0.95);
        cairo_fill_preserve(cr);
        cairo_set_line_width(cr, 0.8);
        cairo_set_source_rgba(cr, 0.02, 0.10, 0.15, 0.94);
        cairo_stroke(cr);
    }

    for (size_t i = 0; i < placed_count; i++) {
        struct Bubble *bubble = &bubbles[i];
        int index = bubble->country;
        rounded_rectangle(cr, bubble->x, bubble->y, bubble->width,
                          bubble->height, 3.0);
        cairo_set_source_rgba(cr, 0.015, 0.10, 0.16, 0.82);
        cairo_fill_preserve(cr);
        cairo_set_line_width(cr, index == front_country ? 1.0 : 0.65);
        set_continent_color(cr, countries[index].continent,
                            index == front_country ? 0.92 : 0.48);
        cairo_stroke(cr);

        if (index == front_country)
            cairo_select_font_face(cr, "Sans", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_BOLD);
        else
            cairo_select_font_face(cr, "Sans", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_NORMAL);
        if (index == front_country)
            cairo_set_source_rgba(cr, 0.96, 1.0, 1.0, 1.0);
        else
            cairo_set_source_rgba(cr, 0.88, 0.95, 0.97, 1.0);
        show_fitted_text(cr, countries[index].name, bubble->x + 5.0,
                         bubble->y + bubble->font_size + 1.0,
                         bubble->width - 10.0, bubble->font_size);

        if (index == front_country) {
            char detail[64];
            snprintf(detail, sizeof detail, "%s - %s",
                     continent_name(countries[index].continent), countries[index].local_time);
            cairo_select_font_face(cr, "Sans", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_NORMAL);
            cairo_set_font_size(cr, 6.2);
            cairo_set_source_rgba(cr, 0.58, 0.91, 0.91, 1.0);
            cairo_move_to(cr, bubble->x + 5.0,
                          bubble->y + bubble->font_size + 8.0);
            cairo_show_text(cr, detail);
        }
    }

    cairo_destroy(cr);
    cairo_surface_destroy(surface);
}

static void render_centered_network(uint32_t *pixels) {
    enum { CALLOUTS_PER_SIDE = 6, CALLOUT_COUNT = CALLOUTS_PER_SIDE * 2 };
    struct CountryPoint points[MAX_COUNTRIES];
    int selected[CALLOUT_COUNT];
    int side_selected[2][CALLOUTS_PER_SIDE];
    int side_counts[2] = {0, 0};
    int selected_count = 0;
    double label_centers[MAX_COUNTRIES] = {0};
    const double center_x = globe_cx;
    const double panel_w = 140.0, panel_h = 42.0;
    const double globe_left = outside_x + PAD;
    const double globe_right = outside_x + 2.0 * R + PAD;

    for (size_t i = 0; i < country_count; i++) {
        project_country(i, &points[i]);
    }

    for (int side = 0; side < 2; side++) {
        for (int n = 0; n < CALLOUTS_PER_SIDE; n++) {
            int best = -1;
            double best_score = -1e9;
            for (size_t i = 0; i < country_count; i++) {
                if (points[i].depth <= 0.05) continue;
                int candidate_side = points[i].x < center_x ? 0 : 1;
                if (candidate_side != side) continue;
                int already_selected = 0;
                double nearest = 2.0 * R;
                for (int j = 0; j < side_counts[side]; j++) {
                    int previous = side_selected[side][j];
                    if (previous == (int)i) already_selected = 1;
                    double dx = points[i].x - points[previous].x;
                    double dy = points[i].y - points[previous].y;
                    nearest = fmin(nearest, hypot(dx, dy));
                }
                if (already_selected) continue;
                double score = points[i].depth + fmin(nearest / 180.0, 0.35);
                if (score > best_score) {
                    best_score = score;
                    best = (int)i;
                }
            }
            if (best < 0) break;
            side_selected[side][side_counts[side]++] = best;
            selected[selected_count++] = best;
        }
    }
    for (int side = 0; side < 2; side++) {
        for (int i = 1; i < side_counts[side]; i++) {
            int index = side_selected[side][i];
            int position = i;
            while (position > 0 &&
                   points[side_selected[side][position - 1]].y > points[index].y) {
                side_selected[side][position] = side_selected[side][position - 1];
                position--;
            }
            side_selected[side][position] = index;
        }

        double min_center = panel_h * 0.5 + 8.0;
        double max_center = H - panel_h * 0.5 - 8.0;
        for (int i = 0; i < side_counts[side]; i++) {
            int index = side_selected[side][i];
            label_centers[index] = fmin(max_center,
                fmax(min_center, points[index].y));
            if (i > 0) {
                int previous = side_selected[side][i - 1];
                label_centers[index] = fmax(label_centers[index],
                    label_centers[previous] + panel_h + 8.0);
            }
        }
        if (side_counts[side] > 0) {
            int last = side_selected[side][side_counts[side] - 1];
            double overflow = label_centers[last] - max_center;
            if (overflow > 0.0) {
                for (int i = 0; i < side_counts[side]; i++)
                    label_centers[side_selected[side][i]] -= overflow;
            }
        }
    }

    cairo_surface_t *surface = cairo_image_surface_create_for_data(
        (unsigned char *)pixels, CAIRO_FORMAT_ARGB32, W, H, W * 4);
    if (cairo_surface_status(surface) != CAIRO_STATUS_SUCCESS) {
        cairo_surface_destroy(surface);
        return;
    }
    cairo_surface_mark_dirty(surface);
    cairo_t *cr = cairo_create(surface);

    cairo_set_line_width(cr, 1.0);
    cairo_set_line_cap(cr, CAIRO_LINE_CAP_ROUND);
    cairo_set_source_rgba(cr, 0.43, 0.91, 1.0, 0.66);
    for (int n = 0; n < selected_count; n++) {
        int index = selected[n];
        int left_side = points[index].x < center_x;
        double node_x = left_side ? globe_left - panel_w - 8.0 : globe_right + 8.0;
        double panel_center_y = label_centers[index];
        double panel_y = panel_center_y - panel_h * 0.5;
        double panel_edge = left_side ? node_x + panel_w : node_x;

        cairo_move_to(cr, points[index].x, points[index].y);
        cairo_line_to(cr, panel_edge, panel_center_y);
        cairo_stroke(cr);

        rounded_rectangle(cr, node_x, panel_y, panel_w, panel_h, 5.0);
        cairo_set_source_rgba(cr, 0.02, 0.20, 0.32, 0.88);
        cairo_fill_preserve(cr);
        cairo_set_line_width(cr, 1.0);
        cairo_set_source_rgba(cr, 0.46, 0.89, 1.0, 0.92);
        cairo_stroke(cr);

        cairo_select_font_face(cr, "Sans", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_BOLD);
        cairo_set_source_rgba(cr, 0.96, 0.99, 1.0, 1.0);
        show_fitted_text(cr, countries[index].name, node_x + 6.0,
                         panel_y + 12.0, panel_w - 12.0, 9.0);
        cairo_select_font_face(cr, "Sans", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_NORMAL);
        cairo_set_font_size(cr, 8.0);
        cairo_set_source_rgba(cr, 0.72, 0.91, 1.0, 1.0);
        cairo_move_to(cr, node_x + 6.0, panel_y + 24.0);
        cairo_show_text(cr, continent_name(countries[index].continent));
        cairo_set_source_rgba(cr, 0.65, 1.0, 0.88, 1.0);
        cairo_move_to(cr, node_x + 6.0, panel_y + 36.0);
        cairo_show_text(cr, countries[index].local_time);
    }

    for (size_t i = 0; i < country_count; i++) {
        if (points[i].depth <= 0.0) continue;
        int highlighted = 0;
        for (int j = 0; j < selected_count; j++) {
            if (selected[j] == (int)i) highlighted = 1;
        }
        double depth = fmin(points[i].depth, 1.0);
        double radius = highlighted ? 4.8 : 1.5 + depth * 0.7;
        double alpha = highlighted ? 0.95 : 0.32 + depth * 0.42;
        if (highlighted) {
            cairo_arc(cr, points[i].x, points[i].y, radius + 2.4, 0, 2 * M_PI);
            cairo_set_source_rgba(cr, 0.15, 0.82, 1.0, 0.22);
            cairo_fill(cr);
            cairo_arc(cr, points[i].x, points[i].y, radius, 0, 2 * M_PI);
            cairo_set_line_width(cr, 1.2);
            cairo_set_source_rgba(cr, 0.70, 0.95, 1.0, 0.96);
            cairo_stroke(cr);
        }
        cairo_arc(cr, points[i].x, points[i].y, highlighted ? 1.8 : radius,
                  0, 2 * M_PI);
        cairo_set_source_rgba(cr, 0.78, 0.96, 1.0, alpha);
        cairo_fill(cr);
    }

    cairo_destroy(cr);
    cairo_surface_destroy(surface);
}

static void render_buffer(uint32_t *pixels) {
    memset(pixels, 0, (size_t)W * H * sizeof(*pixels));
    globe_render(globe, pixels + (size_t)OUTSIDE_Y * W + outside_x, W,
                 lon0, lat0, globe_color_rgb,
                 globe_land_color_rgb, globe_opacity);
    int returning_to_dock = animating && anim_target_docked;
    double clip_boundary = dock_cx;
    if (returning_to_dock) {
        double center_x = surface_x + globe_cx;
        double center_y = surface_y + globe_cy;
        double distance = hypot(center_x - dock_cx, center_y - dock_cy);
        clip_boundary -= 32.0 * fmin(1.0, distance / R);
    }
    int clip_x = (docked || returning_to_dock)
        ? (int)ceil(clip_boundary - surface_x) : 0;
    if (clip_x > W) clip_x = W;
    if (clip_x > 0) {
        for (int y = 0; y < H; y++)
            memset(pixels + (size_t)y * W, 0, (size_t)clip_x * sizeof(*pixels));
    }
    if (globe_is_centered()) {
        if (outside_x >= 300) render_centered_network(pixels);
        else render_country_atlas(pixels);
    }
}

static void on_signal(int s) { (void)s; running = 0; }
static void on_settings_signal(int s) { (void)s; settings_changed = 1; }

static void load_globe_settings(void) {
    FILE *file = fopen(settings_path, "r");
    if (!file) return;
    char line[128];
    while (fgets(line, sizeof line, file)) {
        double value;
        if (sscanf(line, "speed=%lf", &value) == 1) {
            if (value < 0.0) value = 0.0;
            if (value > 40.0) value = 40.0;
            spin = value * M_PI / 180.0;
        } else if (sscanf(line, "opacity=%lf", &value) == 1) {
            if (value < 20.0) value = 20.0;
            if (value > 100.0) value = 100.0;
            globe_opacity = (float)(value / 100.0);
        } else if (strncmp(line, "color=", 6) == 0) {
            char *end = NULL;
            unsigned long color = strtoul(line + 6, &end, 16);
            if (end != line + 6 && color <= 0xfffffful)
                globe_color_rgb = (uint32_t)color;
        } else if (strncmp(line, "land_color=", 11) == 0) {
            char *end = NULL;
            unsigned long color = strtoul(line + 11, &end, 16);
            if (end != line + 11 && color <= 0xfffffful)
                globe_land_color_rgb = (uint32_t)color;
        }
    }
    fclose(file);
}

static int globe_settings_file_changed(void) {
    struct stat current;
    if (stat(settings_path, &current) < 0) return 0;
    if (!settings_snapshot_ready) {
        settings_snapshot = current;
        settings_snapshot_ready = 1;
        return 1;
    }
    int changed = current.st_dev != settings_snapshot.st_dev ||
                  current.st_ino != settings_snapshot.st_ino ||
                  current.st_size != settings_snapshot.st_size ||
                  current.st_mtim.tv_sec != settings_snapshot.st_mtim.tv_sec ||
                  current.st_mtim.tv_nsec != settings_snapshot.st_mtim.tv_nsec;
    if (changed) settings_snapshot = current;
    return changed;
}

int main(int argc, char **argv) {
    R = 290; PAD = 6;
    int cx = 74, cy = 403, fps = 20;
    const char *mask = "mask.bin";
    const char *country_data = "countries.tsv";
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--R") && i + 1 < argc) R = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--cx") && i + 1 < argc) cx = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--cy") && i + 1 < argc) cy = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--fps") && i + 1 < argc) fps = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--mask") && i + 1 < argc) mask = argv[++i];
        else if (!strcmp(argv[i], "--countries") && i + 1 < argc) country_data = argv[++i];
        else if (!strcmp(argv[i], "--spin") && i + 1 < argc) spin = atof(argv[++i]) * M_PI / 180.0;
    }
    dock_cx = cx;
    dock_cy = cy;
    const char *home = getenv("HOME");
    snprintf(settings_path, sizeof settings_path, "%s/.config/waybar-aero/globe.conf",
             home ? home : "");
    load_globe_settings();
    load_country_data(country_data);
    update_country_times();
    globe_settings_file_changed();
    if (fps < 5) fps = 5;
    if (fps > 60) fps = 60;

    globe = globe_create(R, PAD, mask);
    if (!globe) return 1;
    int globe_w, globe_h;
    globe_size(globe, &globe_w, &globe_h);
    H = globe_h + 2 * OUTSIDE_Y;
    globe_cy = OUTSIDE_Y + R + PAD;

    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);
    signal(SIGUSR1, on_settings_signal);

    display = wl_display_connect(NULL);
    if (!display) { fprintf(stderr, "globo-layer: nao consegui conectar ao Wayland (rode dentro do Hyprland)\n"); return 1; }
    struct wl_registry *reg = wl_display_get_registry(display);
    wl_registry_add_listener(reg, &reg_listener, NULL);
    wl_display_roundtrip(display);
    wl_display_roundtrip(display);
    if (!compositor || !shm || !layer_shell) {
        fprintf(stderr, "globo-layer: faltam interfaces (compositor/shm/layer-shell)\n");
        return 1;
    }

    outside_x = screen_w > globe_w ? (screen_w - globe_w) / 2 : 144;
    W = globe_w + 2 * outside_x;
    globe_cx = outside_x + R + PAD;

    surface_x = cx - globe_cx;
    surface_y = cy - globe_cy;
    surface = wl_compositor_create_surface(compositor);
    layer_surface = zwlr_layer_shell_v1_get_layer_surface(layer_shell, surface, output,
                                                          ZWLR_LAYER_SHELL_V1_LAYER_BOTTOM, "ultimadesk-globo");
    zwlr_layer_surface_v1_set_size(layer_surface, W, H);
    zwlr_layer_surface_v1_set_anchor(layer_surface, ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP | ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT);
    zwlr_layer_surface_v1_set_margin(layer_surface, surface_y, 0, 0, surface_x);
    zwlr_layer_surface_v1_set_exclusive_zone(layer_surface, -1);
    zwlr_layer_surface_v1_set_keyboard_interactivity(layer_surface, ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE);
    zwlr_layer_surface_v1_add_listener(layer_surface, &ls_listener, NULL);
    set_circle_input_region(1);
    wl_surface_commit(surface);
    while (!configured && wl_display_dispatch(display) != -1) {}

    if (create_buffers() < 0) return 1;

    hypr_events = connect_hypr_events();
    if (hypr_events >= 0) open_windows = count_windows();

    render_buffer(bufs[0].data);
    bufs[0].busy = 1;
    wl_surface_attach(surface, bufs[0].wl, 0, 0);
    wl_surface_damage_buffer(surface, 0, 0, W, H);
    wl_surface_commit(surface);
    wl_display_flush(display);

    double period = 1.0 / fps, next = now(), prev = now();
    while (running) {
        while (wl_display_prepare_read(display) != 0) wl_display_dispatch_pending(display);
        wl_display_flush(display);
        int paused = open_windows > 0 && !rotate_dragging && !move_dragging && !animating;
        double wait = paused ? 0.5 : next - now();
        int ms = wait < 0 ? -1 : (wait > 0 ? (int)(wait * 1000.0) + 1 : 0);
        struct pollfd fds[2] = {
            { .fd = wl_display_get_fd(display), .events = POLLIN },
            { .fd = hypr_events, .events = POLLIN },
        };
        int r = poll(fds, hypr_events >= 0 ? 2 : 1, ms);
        if (r > 0 && (fds[0].revents & POLLIN)) {
            if (wl_display_read_events(display) < 0) break;
        } else {
            wl_display_cancel_read(display);
        }
        if (wl_display_dispatch_pending(display) < 0) break;
        int reload_settings = settings_changed;
        settings_changed = 0;
        if (globe_settings_file_changed()) reload_settings = 1;
        if (reload_settings) {
            load_globe_settings();
            settings_render_pending = 1;
            next = now();
        }
        if (hypr_events >= 0 && (fds[1].revents & POLLIN)) handle_hypr_events();
        double t = now();
        update_country_times();
        paused = open_windows > 0 && !rotate_dragging && !move_dragging && !animating;
        if (paused && !settings_render_pending) {
            prev = t;
            next = t + period;
            continue;
        }
        if (t < next && !settings_render_pending) continue;
        double dt = t - prev; prev = t;
        next = t + period;
        if (dt > 0.25) dt = 0.25;

        if (animating) {
            double u = (t - anim_start) / anim_duration;
            if (u < 0.0) u = 0.0;
            if (u > 1.0) u = 1.0;
            double eased = u * u * (3.0 - 2.0 * u);
            double velocity_integral = u - pow(1.0 - u, 4.0) * 0.25 - 0.25;
            lon0 = wrap_angle(anim_lon + anim_duration *
                (anim_v0 * u + (anim_v1 - anim_v0) * velocity_integral));
            lat0 = wrap_angle(anim_lat + remainder(LAT_HOME - anim_lat, 2.0 * M_PI) * eased);
            set_surface_position(
                anim_center_x + (anim_target_x - anim_center_x) * eased,
                anim_center_y + (anim_target_y - anim_center_y) * eased);
            if (u >= 1.0) {
                animating = 0;
                docked = anim_target_docked;
                if (docked) set_circle_input_region(1);
                vlon = anim_v1;
            }
        } else if (!rotate_dragging && !move_dragging && !paused) {
            lon0 = wrap_angle(lon0 + vlon * dt);
            vlon += (-spin - vlon) * (1.0 - exp(-dt * 1.2));
            lat0 += (LAT_HOME - lat0) * (1.0 - exp(-dt * 0.5));
        }

        struct buf *b = NULL;
        for (int i = 0; i < 2; i++) if (!bufs[i].busy) { b = &bufs[i]; break; }
        if (!b) continue;                       /* compositor ainda segura os dois */
        render_buffer(b->data);
        b->busy = 1;
        wl_surface_attach(surface, b->wl, 0, 0);
        wl_surface_damage_buffer(surface, 0, 0, W, H);
        wl_surface_commit(surface);
        settings_render_pending = 0;
    }
    return 0;
}
