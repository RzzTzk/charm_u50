#include "utils.h"

#define TILE_M 256
#define TILE_N 256
#define TILE_K 128
#define DSP_PER_PE 4

extern "C" {
void mm_large(
    const float* A,  // HBM通道0-7
    const float* B,  // HBM通道8-15
    float* C,        // HBM通道16-23
    int M, int K, int N
) {
    #pragma HLS INTERFACE m_axi port=A offset=slave bundle=gmem0 num_read_outstanding=32
    #pragma HLS INTERFACE m_axi port=B offset=slave bundle=gmem1 num_read_outstanding=32
    #pragma HLS INTERFACE m_axi port=C offset=slave bundle=gmem2 num_write_outstanding=32
    #pragma HLS INTERFACE s_axilite port=return

    float local_A[TILE_M][TILE_K];
    float local_B[TILE_K][TILE_N];
    float local_C[TILE_M][TILE_N] = {0};
    
    #pragma HLS ARRAY_PARTITION variable=local_A cyclic factor=16 dim=1
    #pragma HLS ARRAY_PARTITION variable=local_B cyclic factor=16 dim=2
    #pragma HLS BIND_STORAGE variable=local_A type=ram_2p impl=uram
    #pragma HLS BIND_STORAGE variable=local_B type=ram_2p impl=uram

    for (int ti = 0; ti < M; ti += TILE_M) {
        for (int tj = 0; tj < N; tj += TILE_N) {
            // Burst读取A和B
            read_block(A + ti*K, local_A, TILE_M, TILE_K, K);
            read_block(B + tj, local_B, TILE_K, TILE_N, N);

            // DSP阵列计算
            for (int tk = 0; tk < K; tk += TILE_K) {
                for (int i = 0; i < TILE_M; i++) {
                    for (int j = 0; j < TILE_N; j++) {
                        #pragma HLS PIPELINE II=1
                        float sum = local_C[i][j];
                        for (int k = 0; k < TILE_K; k++) {
                            sum += local_A[i][k] * local_B[k][j];
                        }
                        local_C[i][j] = sum;
                    }
                }
            }

            // Burst写入C
            write_block(C + ti*N + tj, local_C, TILE_M, TILE_N, N);
        }
    }
}
}
