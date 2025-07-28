#include <iostream>
#include <chrono>
#include <ctime>

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

#define MCAP_IMPLEMENTATION
#include <mcap/reader.hpp>

#include <rapidjson/document.h>
#include <rapidjson/stringbuffer.h>
#include <rapidjson/writer.h>


#ifndef DEBUG_OUTPUT
#define DEBUG_OUTPUT 0
#endif


namespace py = pybind11;

enum class field_type {
    UINT64,
    INT64,
    FLOAT64,
    BYTES,  // numpy S character code
    BOOL,
    UNKNOWN
};

struct field_details {
    size_t offset;
    size_t size;
    field_type type;
};

field_type parse_field_type(const std::string& type) {
    if (type == "uint64") return field_type::UINT64;
    if (type == "int64") return field_type::INT64;
    if (type == "float64") return field_type::FLOAT64;
    if (type == "bool") return field_type::BOOL;
    if (type.rfind("bytes", 0) == 0) return field_type::BYTES;
    return field_type::UNKNOWN;
}

std::string field_type_to_string(field_type type) {
    switch (type) {
        case field_type::UINT64: return "uint64";
        case field_type::INT64: return "int64";
        case field_type::FLOAT64: return "float64";
        case field_type::BYTES: return "bytes";
        case field_type::BOOL: return "bool";
        default: return "unknown";
    }
}

/// Generate a map of field name to field details
/// @param dtype numpy dtype
/// @return map of field name to field details (offset, size, type enum)
std::unordered_map<std::string, field_details> get_field_details(const py::dtype& dtype) {
    std::unordered_map<std::string, field_details> details;

    py::list names = dtype.attr("names");
    py::dict fields = dtype.attr("fields");

    for (const auto& name_obj : names) {
        std::string name = py::str(name_obj);
        py::tuple desc = fields[name.c_str()];  // desc = (dtype, offset, [title])
        py::dtype field_dtype = desc[0];

        details[name] = {
            .offset = py::cast<size_t>(desc[1]), 
            .size = py::cast<size_t>(field_dtype.attr("itemsize")), 
            .type = parse_field_type(field_dtype.attr("name").cast<std::string>())
        };

        if (details[name].type == field_type::UNKNOWN) {
            throw std::runtime_error("unknown field type: " + field_dtype.attr("name").cast<std::string>());
        }

#if DEBUG_OUTPUT
        std::cout << ">> name: " << name 
                  << " offset: " << details[name].offset
                  << " size: " << details[name].size
                  << " parsed type: " << field_type_to_string(details[name].type)
                  << std::endl;
#endif
    }
    return details;
}

/// parse given mcap file with data in JSON format into a numpy structured array.
/// @param py_array numpy structured array, initialized in python
/// @param mcap_path path to the mcap file
/// @param topic only parse messages of this topic
/// @return empty string on success, error message on failure
std::string parse_mcap(py::array& py_array, std::string mcap_path, std::string topic, uint64_t start_time_ns)
{
#if DEBUG_OUTPUT
    std::cout << "ARG mcap_path: " << mcap_path << std::endl;
    std::cout << "ARG topic: \"" << topic << "\"  start_time_ns: " << start_time_ns << std::endl;

    auto start_wall = std::chrono::high_resolution_clock::now();
    std::clock_t start_cpu = std::clock();
    
    std::cout << ">> py_array.size(): " << py_array.size() << std::endl;  // number of elements
    std::cout << ">> py_array.itemsize(): " << py_array.itemsize() << std::endl;  // bytes per element
    std::cout << ">> py_array.nbytes(): " << py_array.nbytes() << std::endl;
    std::cout << ">> py_array.data(): " << py_array.data() << std::endl;
    std::cout << ">> py_array.dtype(): " << py::str(py_array.dtype()).cast<std::string>() << std::endl;
    std::cout << ">> py_array.ndim(): " << py_array.ndim() << std::endl;  // number of dimensions
    std::cout << ">> py_array.shape(): (";
    for (ssize_t i = 0; i < py_array.ndim(); ++i) {
        std::cout << py_array.shape(i);
        if (i < py_array.ndim() - 1) std::cout << ", ";
    }
    std::cout << ")" << std::endl;
    std::cout << ">> py_array.strides(): (";
    for (ssize_t i = 0; i < py_array.ndim(); ++i) {
        std::cout << py_array.strides(i);
        if (i < py_array.ndim() - 1) std::cout << ", ";
    }
    std::cout << ")" << std::endl;
#endif

    std::unordered_map<std::string, field_details> details = get_field_details(py_array.dtype());

    mcap::McapReader reader;
    {
        const auto res = reader.open(mcap_path);
        if (!res.ok()) {
            std::cerr << "ERROR: " << res.message << std::endl;
            return "failed to open mcap file";
        }
    }

    // only load specified topic and use a specific start time
    mcap::ReadMessageOptions options;
    options.startTime = start_time_ns;
    options.topicFilter = [topic](std::string_view _topic) {
        return _topic == topic;
    };

    mcap::ProblemCallback problemCallback = [](const mcap::Status& status) {
        std::cerr << "ERROR parse-problem: " << status.message << std::endl;
    };

    mcap::LinearMessageView messageView = reader.readMessages(problemCallback, options);

    size_t cnt = 0;
    size_t num_rows = py_array.size();
    int mod = std::max(static_cast<int>(num_rows / 100.0), 1);
    char* data_ptr = static_cast<char*>(py_array.mutable_data());
    size_t row_stride = py_array.strides(0);

    for (mcap::LinearMessageView::Iterator it = messageView.begin(); it != messageView.end(); it++)
    {
        // skip any non-json-encoded messages.
        if (it->channel->messageEncoding != "json")
        {
            std::cerr << "not a JSON message: " << it->channel->messageEncoding << std::endl;
            continue;
        }

        rapidjson::Document doc;
        if (doc.Parse(reinterpret_cast<const char *>(it->message.data), it->message.dataSize).HasParseError())
        {
            std::cerr << "JSON parse error of message: " << it->message.data << std::endl;
            return std::string("JSON parse error in message ") + std::to_string(cnt);
        }

        char* row_ptr = data_ptr + cnt * row_stride;

        // write timestamp (not in message data)
        *reinterpret_cast<uint64_t*>(row_ptr + details["ts"].offset) = it->message.publishTime;

        // for all fields in doc: write to py_array at position "cnt"
        for (auto it_json = doc.MemberBegin(); it_json != doc.MemberEnd(); ++it_json)
        {
            const char* field = it_json->name.GetString();
            const auto& value = it_json->value;
            
            if (value.IsNull() || value.IsObject()) {
                continue;
            }
            // check if "field" is in dtype
            std::unordered_map<std::string, field_details>::iterator details_it = details.find(field);
            if (details_it == details.end()) {
                continue;
            }

            // don't rely on JSON data types. casts to bigger datatypes are dangerous
            switch (details_it->second.type)
            {
            case field_type::UINT64:
                *reinterpret_cast<uint64_t*>(row_ptr + details_it->second.offset) = value.GetUint64();
                break;
            
            case field_type::INT64:
                *reinterpret_cast<int64_t*>(row_ptr + details_it->second.offset) = value.GetInt64();
                break;
            
            case field_type::FLOAT64:
                *reinterpret_cast<double*>(row_ptr + details_it->second.offset) = value.GetDouble();
                break;
            
            case field_type::BOOL:
                *reinterpret_cast<bool*>(row_ptr + details_it->second.offset) = value.GetBool();
                break;
            
            case field_type::BYTES:
                {
                    const char *myvar = value.GetString();
                    size_t len = details_it->second.size - 1;
                    // std::cout << "field: " << field << " bytes: " << value.GetString() << " len: " << len << " size: " << value.GetStringLength() << std::endl;
                    if (value.GetStringLength() < len) {
                        len = value.GetStringLength();
                    }
                    std::memcpy(row_ptr + details_it->second.offset, myvar, len);
                }
                break;
            
            case field_type::UNKNOWN:
            default:
                std::cout << "ERROR: unknown type: " << value.GetType() << " for field: " << field << std::endl;
                break;
            }
        }

        cnt += 1;
        // print progress
        if (cnt % mod == 0) {
            int percent = static_cast<int>((static_cast<double>(cnt) / num_rows) * 100);
            std::cout << "\r>> Loading " << topic << ": " << percent << "%" << std::flush;
        }
        if (cnt >= num_rows) {
            break;
        }
    }
    reader.close();
    std::cout << "\rLoading " << topic << ": 100% -> loaded " << cnt << " rows of " << num_rows << std::endl;

#if DEBUG_OUTPUT
    std::clock_t end_cpu = std::clock();
    auto end_wall = std::chrono::high_resolution_clock::now();

    double wall_ms = std::chrono::duration<double>(end_wall - start_wall).count();
    double cpu_ms = (double)(end_cpu - start_cpu) / CLOCKS_PER_SEC;

    std::cout << ">> Wall time: " << wall_ms << " s" << std::endl;
    std::cout << ">> CPU time: " << cpu_ms << " s" << std::endl;
#endif

    return "";
}

PYBIND11_MODULE(_core, m)
{
    m.doc() = "parse mcap file and decode JSON messages";

    m.def("parse_mcap", &parse_mcap, "parse mcap file and decode JSON messages",
          py::arg("py_array"), py::arg("mcap_path"), py::arg("topic"), py::arg("start_time_ns") = 0);

#ifdef VERSION_INFO
    m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
    m.attr("__version__") = "dev";
#endif
}
