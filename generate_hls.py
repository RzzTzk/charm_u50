#!/usr/bin/env python3
"""
CHARM Auto-HLS Code Generator with CDSE and CDAC
Usage: 
  python generate_hls.py --model models/bert.json --output design_space/acc_config.json
"""

import json
import os
import numpy as np
from pathlib import Path
from jinja2 import Template
import argparse
import time

# --- Configuration ---
PROJECT_ROOT = Path(__file__).parent.resolve()
KERNEL_DIR = PROJECT_ROOT / "kernels"
INCLUDE_DIR = PROJECT_ROOT / "include" / "kernel"
DESIGN_DIR = PROJECT_ROOT / "design_space"
MODEL_DIR = PROJECT_ROOT / "models"

# --- Hardware Constraints ---
HARDWARE_CONSTRAINTS = {
    "total_dsp": 5952,
    "total_bram": 2688,
    "total_uram": 320,
    "total_hbm_channels": 32,
    "hbm_bandwidth": 460e9,  # GB/s
    "dsp_frequency": 300,    # MHz
}

# --- CDSE: Design Space Exploration for Single Accelerator ---
class CDSE:
    def __init__(self, hardware_constraints):
        self.constraints = hardware_constraints
        
    def explore_design_space(self, M, K, N, acc_type="large"):
        """Explore design space for single accelerator"""
        designs = []
        
        # Tile size candidates based on accelerator type
        if acc_type == "large":
            tile_candidates = [(256, 256, 128), (512, 512, 256), (1024, 1024, 512)]
        else:
            tile_candidates = [(64, 64, 64), (128, 128, 64), (256, 256, 128)]
        
        for tile_m, tile_n, tile_k in tile_candidates:
            # Calculate resource requirements
            dsp_required = self.calculate_dsp(tile_m, tile_n, tile_k, acc_type)
            hbm_channels = self.calculate_hbm_channels(tile_m, tile_n, tile_k)
            mem_required = self.calculate_memory(tile_m, tile_n, tile_k)
            
            # Check constraints
            if (dsp_required <= self.constraints["total_dsp"] and
                hbm_channels <= self.constraints["total_hbm_channels"] and
                mem_required["bram"] <= self.constraints["total_bram"] and
                mem_required["uram"] <= self.constraints["total_uram"]):
                
                # Estimate performance
                throughput = self.estimate_throughput(M, K, N, tile_m, tile_n, tile_k, dsp_required)
                efficiency = throughput / (dsp_required * self.constraints["dsp_frequency"] * 2e-3)  # TFLOPS/DSP
                
                designs.append({
                    "type": acc_type,
                    "tile": [tile_m, tile_n, tile_k],
                    "dsp": dsp_required,
                    "hbm_channels": {"start": 0, "count": hbm_channels},
                    "throughput": throughput,
                    "efficiency": efficiency,
                    "memory": mem_required
                })
        
        # Sort by throughput and return top designs
        return sorted(designs, key=lambda x: x["throughput"], reverse=True)[:3]
    
    def calculate_dsp(self, tile_m, tile_n, tile_k, acc_type):
        """Calculate required DSP count"""
        if acc_type == "large":
            # High parallelism for large matrices
            return min(self.constraints["total_dsp"], (tile_m * tile_n) // 16)
        else:
            # Moderate parallelism for small matrices
            return min(512, (tile_m * tile_n) // 32)
    
    def calculate_hbm_channels(self, tile_m, tile_n, tile_k):
        """Calculate required HBM channels"""
        # Each channel ~2GB/s, estimate based on data volume
        data_volume = (tile_m * tile_k + tile_k * tile_n) * 4  # bytes
        return max(1, min(16, int(np.ceil(data_volume / (128 * 1024))))  # 128KB per channel
    
    def calculate_memory(self, tile_m, tile_n, tile_k):
        """Calculate memory requirements"""
        return {
            "bram": (tile_m * tile_k + tile_k * tile_n) * 4 // 1024,  # KB
            "uram": (tile_m * tile_n) * 4 // 4096  # URAM blocks
        }
    
    def estimate_throughput(self, M, K, N, tile_m, tile_n, tile_k, dsp_count):
        """Estimate throughput in GFLOPS"""
        # Simplified performance model
        ops = 2 * M * K * N  # Total operations
        cycles = (M/tile_m) * (N/tile_n) * (K/tile_k) * (tile_m * tile_n * tile_k) / dsp_count
        time_sec = cycles / (self.constraints["dsp_frequency"] * 1e6)
        return ops / time_sec / 1e9  # GFLOPS

# --- CDAC: Diverse Accelerator Composer ---
class CDAC:
    def __init__(self, cdse):
        self.cdse = cdse
        
    def compose_accelerators(self, model_file, num_accs=2):
        """Compose heterogeneous accelerators for given model"""
        with open(model_file) as f:
            model = json.load(f)
        
        # Group kernels by size
        large_kernels = []
        small_kernels = []
        
        for layer in model["layers"]:
            if layer["type"] == "mm":
                ops = layer["M"] * layer["K"] * layer["N"]
                if ops > 1e6:  # Large matrix
                    large_kernels.append(layer)
                else:
                    small_kernels.append(layer)
        
        # Allocate resources proportionally
        total_ops = sum(k["M"]*k["K"]*k["N"] for k in large_kernels + small_kernels)
        large_ratio = sum(k["M"]*k["K"]*k["N"] for k in large_kernels) / total_ops
        
        # Design accelerators
        accelerators = []
        
        if large_kernels and large_ratio > 0.7:
            # Large matrix accelerator
            avg_size = self.get_average_size(large_kernels)
            designs = self.cdse.explore_design_space(
                avg_size["M"], avg_size["K"], avg_size["N"], "large"
            )
            if designs:
                accelerators.append(designs[0])  # Best design
        
        if small_kernels and len(accelerators) < num_accs:
            # Small matrix accelerator
            avg_size = self.get_average_size(small_kernels)
            designs = self.cdse.explore_design_space(
                avg_size["M"], avg_size["K"], avg_size["N"], "small"
            )
            if designs:
                accelerators.append(designs[0])
        
        # Assign HBM channels
        self.assign_hbm_channels(accelerators)
        
        return {
            "accelerators": accelerators,
            "model": model["name"],
            "total_throughput": sum(acc["throughput"] for acc in accelerators)
        }
    
    def get_average_size(self, kernels):
        """Calculate average matrix size"""
        total_M = sum(k["M"] for k in kernels)
        total_K = sum(k["K"] for k in kernels)
        total_N = sum(k["N"] for k in kernels)
        count = len(kernels)
        return {"M": total_M//count, "K": total_K//count, "N": total_N//count}
    
    def assign_hbm_channels(self, accelerators):
        """Assign HBM channels to avoid conflicts"""
        next_channel = 0
        for acc in accelerators:
            channels_needed = acc["hbm_channels"]["count"]
            acc["hbm_channels"]["start"] = next_channel
            next_channel += channels_needed

# --- HLS Code Generation ---
class HLSGenerator:
    def __init__(self):
        self.kernel_template = Template("""// Auto-generated by CHARM CDSE-CDAC
#include "utils.h"

#define TILE_M {{tile_m}}
#define TILE_N {{tile_n}}
#define TILE_K {{tile_k}}

extern "C" {
void {{kernel_name}}(
    const float* A,  // HBM channel {{hbm_start}} to {{hbm_end}}
    const float* B,  // HBM channel {{hbm_b_start}} to {{hbm_b_end}}
    float* C,
    int M, int K, int N
) {
    #pragma HLS INTERFACE m_axi port=A offset=slave bundle=gmem{{bundle_a}}
    #pragma HLS INTERFACE m_axi port=B offset=slave bundle=gmem{{bundle_b}}
    #pragma HLS INTERFACE m_axi port=C offset=slave bundle=gmem{{bundle_a}}
    #pragma HLS INTERFACE s_axilite port=return
    {{dataflow_pragma}}

    float local_A[TILE_M][TILE_K];
    float local_B[TILE_K][TILE_N];
    #pragma HLS ARRAY_PARTITION variable=local_A cyclic factor={{partition_factor}} dim=1
    #pragma HLS ARRAY_PARTITION variable=local_B cyclic factor={{partition_factor}} dim=2
    #pragma HLS BIND_STORAGE variable=local_A type=ram_2p impl={{mem_type}}
    #pragma HLS BIND_STORAGE variable=local_B type=ram_2p impl={{mem_type}}

    {% if is_large %}
    for (int ti = 0; ti < M; ti += TILE_M) {
        for (int tj = 0; tj < N; tj += TILE_N) {
            #pragma HLS LOOP_FLATTEN
            read_block<float, TILE_M, TILE_K>(A + ti*K, local_A, TILE_M, TILE_K, K);
            read_block<float, TILE_K, TILE_N>(B + tj, local_B, TILE_K, TILE_N, N);

            for (int tk = 0; tk < K; tk += TILE_K) {
                for (int i = 0; i < TILE_M; i++) {
                    for (int j = 0; j < TILE_N; j++) {
                        #pragma HLS PIPELINE II=1
                        float sum = 0;
                        for (int k = 0; k < TILE_K; k++) {
                            sum += local_A[i][k] * local_B[k][j];
                        }
                        C[(ti+i)*N + (tj+j)] = sum;
                    }
                }
            }
        }
    }
    {% else %}
    hls::stream<float> a_stream, b_stream;
    #pragma HLS STREAM variable=a_stream depth=32
    #pragma HLS STREAM variable=b_stream depth=32

    load_A: for(int i = 0; i < M*K; i++) {
        #pragma HLS PIPELINE II=1
        a_stream.write(A[i]);
    }

    load_B: for(int i = 0; i < K*N; i++) {
        #pragma HLS PIPELINE II=1
        b_stream.write(B[i]);
    }

    compute: for(int i = 0; i < M; i++) {
        for(int j = 0; j < N; j++) {
            #pragma HLS PIPELINE II=1
            float sum = 0;
            for(int k = 0; k < K; k++) {
                sum += a_stream.read() * b_stream.read();
            }
            C[i*N + j] = sum;
        }
    }
    {% endif %}
}
}
""")

    def generate_kernels(self, acc_config, output_dir):
        """Generate HLS kernels from accelerator configuration"""
        (INCLUDE_DIR).mkdir(parents=True, exist_ok=True)
        (KERNEL_DIR).mkdir(exist_ok=True)
        
        # Generate utils header
        self.generate_utils_header()
        
        # Generate each accelerator
        for i, acc in enumerate(acc_config["accelerators"]):
            is_large = acc["type"] == "large"
            self.generate_kernel(acc, i, is_large)
        
        print(f"Generated {len(acc_config['accelerators'])} accelerators")
    
    def generate_utils_header(self):
        """Generate kernel utilities header"""
        utils_code = """#ifndef KERNEL_UTILS_H
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
}

#endif
"""
        with open(INCLUDE_DIR / "utils.h", "w") as f:
            f.write(utils_code)
    
    def generate_kernel(self, acc, index, is_large):
        """Generate individual kernel"""
        template_vars = {
            "kernel_name": f"mm_{acc['type']}",
            "tile_m": acc["tile"][0],
            "tile_n": acc["tile"][1],
            "tile_k": acc["tile"][2],
            "hbm_start": acc["hbm_channels"]["start"],
            "hbm_end": acc["hbm_channels"]["start"] + acc["hbm_channels"]["count"] // 2 - 1,
            "hbm_b_start": acc["hbm_channels"]["start"] + acc["hbm_channels"]["count"] // 2,
            "hbm_b_end": acc["hbm_channels"]["start"] + acc["hbm_channels"]["count"] - 1,
            "bundle_a": 0 if is_large else 1,
            "bundle_b": 1 if is_large else 2,
            "partition_factor": min(32, acc["tile"][0]//4) if is_large else 1,
            "mem_type": "uram" if is_large else "bram",
            "dataflow_pragma": "#pragma HLS DATAFLOW" if is_large else "",
            "is_large": is_large
        }
        
        kernel_code = self.kernel_template.render(template_vars)
        kernel_path = KERNEL_DIR / f"mm_{acc['type']}.cpp"
        
        with open(kernel_path, "w") as f:
            f.write(kernel_code)
        print(f"  Generated {kernel_path}")

# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(description="CHARM CDSE-CDAC with HLS Generation")
    parser.add_argument("--model", required=True, help="Input model JSON file")
    parser.add_argument("--output", default="design_space/acc_config.json", help="Output config file")
    parser.add_argument("--num_accs", type=int, default=2, help="Number of accelerators")
    args = parser.parse_args()
    
    # Create directories
    (DESIGN_DIR).mkdir(exist_ok=True)
    (MODEL_DIR).mkdir(exist_ok=True)
    
    print("=== CHARM CDSE-CDAC Optimization ===")
    
    # Run CDSE-CDAC
    cdse = CDSE(HARDWARE_CONSTRAINTS)
    cdac = CDAC(cdse)
    
    print(f"Optimizing for model: {args.model}")
    start_time = time.time()
    
    acc_config = cdac.compose_accelerators(args.model, args.num_accs)
    optimization_time = time.time() - start_time
    
    # Save configuration
    with open(args.output, "w") as f:
        json.dump(acc_config, f, indent=2)
    
    print(f"Optimization completed in {optimization_time:.2f}s")
    print(f"Total throughput: {acc_config['total_throughput']:.2f} GFLOPS")
    
    # Generate HLS code
    print("\n=== Generating HLS Code ===")
    hls_gen = HLSGenerator()
    hls_gen.generate_kernels(acc_config, KERNEL_DIR)
    
    print(f"\nConfiguration saved to: {args.output}")
    print("HLS code generation completed!")

if __name__ == "__main__":
    main()