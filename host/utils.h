// host/utils.h
#ifndef _UTILS_H_
#define _UTILS_H_

#include <CL/cl2.hpp>
#include <vector>
#include <fstream>
#include <stdexcept>

// 声明函数
cl::Device get_xilinx_device();
cl::Program load_xclbin(cl::Context& context, const std::string& xclbin_path);

// 实现函数
inline cl::Device get_xilinx_device() {
    std::vector<cl::Platform> platforms;
    cl::Platform::get(&platforms);
    
    for (const auto& plat : platforms) {
        std::string plat_name = plat.getInfo<CL_PLATFORM_NAME>();
        if (plat_name.find("Xilinx") != std::string::npos) {
            std::vector<cl::Device> devices;
            plat.getDevices(CL_DEVICE_TYPE_ACCELERATOR, &devices);
            if (!devices.empty()) {
                return devices[0];
            }
        }
    }
    throw std::runtime_error("No Xilinx device found!");
}

inline cl::Program load_xclbin(cl::Context& context, const std::string& xclbin_path) {
    std::ifstream bin_file(xclbin_path, std::ifstream::binary);
    if (!bin_file) {
        throw std::runtime_error("Failed to open xclbin file: " + xclbin_path);
    }
    
    bin_file.seekg(0, bin_file.end);
    size_t size = bin_file.tellg();
    bin_file.seekg(0, bin_file.beg);
    char* buf = new char[size];
    bin_file.read(buf, size);
    
    cl::Program::Binaries bins{{buf, size}};
    cl::Program program(context, {context.getInfo<CL_CONTEXT_DEVICES>()[0]}, bins);
    delete[] buf;
    
    return program;
}

#endif