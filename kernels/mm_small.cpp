#include "utils.h"

extern "C" {
void mm_small(
    const float* A,  // HBM通道24-27
    const float* B,  // HBM通道28-31
    float* C,        // HBM通道24-27
    int M, int K, int N
) {
    #pragma HLS INTERFACE m_axi port=A bundle=gmem3 latency=50
    #pragma HLS INTERFACE m_axi port=B bundle=gmem4 latency=50
    #pragma HLS INTERFACE m_axi port=C bundle=gmem3 latency=50
    #pragma HLS INTERFACE s_axilite port=return
    #pragma HLS DATAFLOW

    hls::stream<float> a_stream("a_stream");
    hls::stream<float> b_stream("b_stream");
    hls::stream<float> c_stream("c_stream");

    // 数据加载
    load_A: for(int i = 0; i < M*K; i++) {
        #pragma HLS PIPELINE II=1
        a_stream.write(A[i]);
    }
    load_B: for(int i = 0; i < K*N; i++) {
        #pragma HLS PIPELINE II=1
        b_stream.write(B[i]);
    }

    // 计算核心
    compute: for(int i = 0; i < M; i++) {
        for(int j = 0; j < N; j++) {
            #pragma HLS PIPELINE II=1
            float sum = 0;
            for(int k = 0; k < K; k++) {
                sum += a_stream.read() * b_stream.read();
            }
            c_stream.write(sum);
        }
    }

    // 结果写回
    store_C: for(int i = 0; i < M*N; i++) {
        #pragma HLS PIPELINE II=1
        C[i] = c_stream.read();
    }
}
}