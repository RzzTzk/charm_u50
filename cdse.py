import numpy as np

class CDSE:
    def __init__(self, hardware_constraints):
        self.constraints = hardware_constraints

    def explore_design_space(self, M, K, N, acc_type="large"):
        designs = []

        if acc_type == "large":
            tile_candidates = [(256, 256, 128), (512, 512, 256), (1024, 1024, 512)]
        else:
            tile_candidates = [(64, 64, 64), (128, 128, 64), (256, 256, 128)]

        for tile_m, tile_n, tile_k in tile_candidates:
            dsp_required = self.calculate_dsp(tile_m, tile_n, tile_k, acc_type)
            hbm_channels = self.calculate_hbm_channels(tile_m, tile_n, tile_k)
            mem_required = self.calculate_memory(tile_m, tile_n, tile_k)

            if (dsp_required <= self.constraints["total_dsp"] and
                hbm_channels <= self.constraints["total_hbm_channels"] and
                mem_required["bram"] <= self.constraints["total_bram"] and
                mem_required["uram"] <= self.constraints["total_uram"]):

                throughput, efficiency = self.estimate_throughput(M, K, N, dsp_required)

                designs.append({
                    "type": acc_type,
                    "tile": f"{tile_m}x{tile_n}x{tile_k}",
                    "dsp": dsp_required,
                    "bram_blocks": mem_required["bram"],
                    "uram_blocks": mem_required["uram"],
                    "hbm_channels": hbm_channels,
                    "throughput_GFLOPS": round(throughput, 2),
                    "efficiency": round(efficiency, 3)
                })

        # 按吞吐量排序
        return sorted(designs, key=lambda x: x["throughput_GFLOPS"], reverse=True)

    def calculate_dsp(self, tile_m, tile_n, tile_k, acc_type):
        if acc_type == "large":
            return min(self.constraints["total_dsp"], (tile_m * tile_n) // 16)
        else:
            return min(512, (tile_m * tile_n) // 32)

    def calculate_hbm_channels(self, tile_m, tile_n, tile_k):
        data_volume = (tile_m * tile_k + tile_k * tile_n + tile_m * tile_n) * 4
        required_bw = data_volume * self.constraints["dsp_frequency"] / (tile_m * tile_n)
        channels = int(np.ceil(required_bw / self.constraints["hbm_bw_per_channel"]))
        return max(1, min(self.constraints["total_hbm_channels"], channels))

    def calculate_memory(self, tile_m, tile_n, tile_k):
        bram_bytes = (tile_m * tile_k + tile_k * tile_n) * 4
        uram_bytes = (tile_m * tile_n) * 4
        return {
            "bram": int(np.ceil(bram_bytes / 4608)),   # BRAM=4.5KB
            "uram": int(np.ceil(uram_bytes / 36864))  # URAM=36KB
        }

    def estimate_throughput(self, M, K, N, dsp_count):
        peak = dsp_count * 2 * self.constraints["dsp_frequency"]
        throughput = peak / 1e9  # GFLOPS
        efficiency = (throughput * 1e9) / peak
        return throughput, efficiency


# --- 示例运行 ---
constraints = {
    "total_dsp": 8000,
    "total_bram": 2000,
    "total_uram": 512,
    "total_hbm_channels": 32,
    "hbm_bw_per_channel": 32e9,  # 32 GB/s
    "dsp_frequency": 1.0e9       # 1 GHz
}

cdse = CDSE(constraints)
results = cdse.explore_design_space(M=4096, K=4096, N=4096, acc_type="large")

for r in results:
    print(r)
