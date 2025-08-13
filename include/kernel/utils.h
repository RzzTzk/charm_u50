#ifndef KERNEL_UTILS_H
#define KERNEL_UTILS_H

#include <ap_int.h>
#include <hls_stream.h>

template<typename T, int DIM1, int DIM2>
void read_block(const T* src, T dst[DIM1][DIM2], int rows, int cols, int ld) {
    #pragma HLS INLINE
    for (int i = 0; i < rows; i++) {
        #pragma HLS PIPELINE II=1
        for (int j = 0; j < cols; j++) {
            dst[i][j] = src[i*ld + j];
        }
    }
    static_assert(DIM1 >= rows && DIM2 >= cols, "Dimensions mismatch");
}

template<typename T, int DIM1, int DIM2>
void write_block(T* dst, const T src[DIM1][DIM2], int rows, int cols, int ld) {
    #pragma HLS INLINE
    for (int i = 0; i < rows; i++) {
        #pragma HLS PIPELINE II=1
        for (int j = 0; j < cols; j++) {
            dst[i*ld + j] = src[i][j];
        }
    }
    static_assert(DIM1 >= rows && DIM2 >= cols, "Dimensions mismatch");
}

#endif