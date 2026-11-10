// Wokwi cannot simulate resistor dividers on analog signals. Model two
// 10k/15k dividers here: 0..5V becomes 0..3V, without inverting DOUT.
// This is a simulation model, not an extra component for physical hardware.
#include "wokwi-api.h"
#include <stdlib.h>

typedef struct {
    pin_t analog_in;
    pin_t analog_out;
    pin_t digital_in;
    pin_t digital_out;
} chip_state_t;

static void update(void *user_data) {
    chip_state_t *chip = user_data;
    pin_dac_write(chip->analog_out, pin_adc_read(chip->analog_in) * 0.6f);
    // Digital simulation uses logic levels; HIGH represents the divided 3V.
    pin_write(chip->digital_out, pin_read(chip->digital_in));
}

void chip_init(void) {
    chip_state_t *chip = malloc(sizeof(chip_state_t));
    chip->analog_in = pin_init("A5V", ANALOG);
    chip->analog_out = pin_init("A3V", ANALOG);
    chip->digital_in = pin_init("D5V", INPUT);
    chip->digital_out = pin_init("D3V", OUTPUT_HIGH);
    const timer_config_t timer_config = {.callback = update, .user_data = chip};
    timer_t timer = timer_init(&timer_config);
    timer_start(timer, 1000, true);
}
