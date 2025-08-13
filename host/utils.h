// host/utils.h
#ifndef _UTILS_H_
#define _UTILS_H_

#include <CL/cl2.hpp>
#include <vector>
#include <fstream>
#include <stdexcept>

cl::Device get_xilinx_device();
cl::Program load_xclbin(cl::Context& context, const std::string& xclbin_path);

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
    
    // 读取二进制文件
    bin_file.seekg(0, bin_file.end);
    size_t size = bin_file.tellg();
    bin_file.seekg(0, bin_file.beg);
    std::vector<unsigned char> bin_data(size);
    bin_file.read(reinterpret_cast<char*>(bin_data.data()), size);
    
    // 创建Program对象
    cl::Program::Binaries binaries{bin_data};
    auto devices = context.getInfo<CL_CONTEXT_DEVICES>();
    return cl::Program(context, devices, binaries);
}

#endif