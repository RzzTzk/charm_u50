import json


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

        return sorted(designs, key=lambda x: x["throughput_GFLOPS"], reverse=True)

    def calculate_dsp(self, tile_m, tile_n, tile_k, acc_type):
        if acc_type == "large":
            return min(self.constraints["total_dsp"], (tile_m * tile_n) // 16)
        else:
            return min(512, (tile_m * tile_n) // 32)

    def calculate_hbm_channels(self, tile_m, tile_n, tile_k):
        data_volume = (tile_m * tile_k + tile_k * tile_n + tile_m * tile_n) * 4
        required_bw = data_volume * self.constraints["dsp_frequency"] / (tile_m * tile_n)
        channels = int(-(-required_bw // self.constraints["hbm_bw_per_channel"])) 
        return max(1, min(self.constraints["total_hbm_channels"], channels))

    def calculate_memory(self, tile_m, tile_n, tile_k):
        bram_bytes = (tile_m * tile_k + tile_k * tile_n) * 4
        uram_bytes = (tile_m * tile_n) * 4
        return {
            "bram": int(-(-bram_bytes // 4608)),   # BRAM block 4.5KB，
            "uram": int(-(-uram_bytes // 36864))  # URAM block 36KB，
        }

    def estimate_throughput(self, M, K, N, dsp_count):
        peak = dsp_count * 2 * self.constraints["dsp_frequency"]
        throughput = peak / 1e9  # GFLOPS
        efficiency = (throughput * 1e9) / peak
        return throughput, efficiency



class CDAC:
    def __init__(self, cdse):
        self.cdse = cdse
        
    def compose_accelerators(self, model_file, num_accs=2):
        with open(model_file) as f:
            model = json.load(f)
        
       
        large_kernels, small_kernels = [], []
        for layer in model["layers"]:
            if layer["type"] == "mm":
                ops = layer["M"] * layer["K"] * layer["N"]  
                if ops > 1e6:
                    large_kernels.append(layer)
                else:
                    small_kernels.append(layer)
        
        total_ops = sum(k["M"]*k["K"]*k["N"] for k in large_kernels + small_kernels)
        large_ratio = (sum(k["M"]*k["K"]*k["N"] for k in large_kernels) / total_ops) if total_ops>0 else 0
        
        accelerators = []
        
        if large_kernels and large_ratio > 0.7:
            avg_size = self.get_average_size(large_kernels)
            designs = self.cdse.explore_design_space(avg_size["M"], avg_size["K"], avg_size["N"], "large")
            if designs:
                accelerators.append(designs[0])
        
        if small_kernels and len(accelerators) < num_accs:
            avg_size = self.get_average_size(small_kernels)
            designs = self.cdse.explore_design_space(avg_size["M"], avg_size["K"], avg_size["N"], "small")
            if designs:
                accelerators.append(designs[0])
        
        self.assign_hbm_channels(accelerators)
        
        return {
            "accelerators": accelerators,
            "model": model.get("name","unknown"),
            "total_throughput_GFLOPS": sum(acc["throughput_GFLOPS"] for acc in accelerators)
        }
    
    def get_average_size(self, kernels):
        count = len(kernels)
        return {
            "M": sum(k["M"] for k in kernels)//count,
            "K": sum(k["K"] for k in kernels)//count,
            "N": sum(k["N"] for k in kernels)//count
        }
    
    def assign_hbm_channels(self, accelerators):
        next_channel = 0
        for acc in accelerators:
            channels_needed = acc["hbm_channels"] if isinstance(acc["hbm_channels"], int) else acc["hbm_channels"]["count"]
            acc["hbm_channels"] = {"start": next_channel, "count": channels_needed}
            next_channel += channels_needed



toy_model = {
  "name": "toy_transformer",
  "layers": [
    {"type": "mm", "M": 4096, "K": 4096, "N": 4096},   # Attention
    {"type": "mm", "M": 1024, "K": 1024, "N": 1024},   # FFN
    {"type": "mm", "M": 128, "K": 128, "N": 128},      # 
    {"type": "softmax"},
    {"type": "layernorm"},
    {"type": "transpose"}
  ]
}

with open("model.json", "w") as f:
    json.dump(toy_model, f, indent=2)


constraints = {
    "total_dsp": 8000,
    "total_bram": 2000,
    "total_uram": 512,
    "total_hbm_channels": 32,
    "hbm_bw_per_channel": 32e9,
    "dsp_frequency": 1.0e9
}

cdse = CDSE(constraints)
cdac = CDAC(cdse)

result = cdac.compose_accelerators("model.json", num_accs=2)

print("Model:", result["model"])
print("Throughput (GFLOPS):", result["total_throughput_GFLOPS"])
print("Acclerators:")
for acc in result["accelerators"]:
    print(acc)
