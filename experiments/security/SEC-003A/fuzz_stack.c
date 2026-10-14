#include <stdint.h>
#include <stddef.h>

__attribute__((noinline))
static void process(const int8_t *d, size_t n) {
    volatile uint8_t buffer[8] = {0};

    if (n < 3) return;

    if (d[0] == 'S' &&
        d[1] == 'V' &&
        d[2] == '!') {
        for (size_t i = 0; i < 16; i++) {
            buffer[i] = (uint8_t)i;
        }
    }
}

int LLVMFuzzerTestOneInput(
    const uint8_t *data, size_t size
) {
    process(data, size);
    return 0;
}
