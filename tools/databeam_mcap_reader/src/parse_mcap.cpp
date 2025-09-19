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
    ARRAY,
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
    if (type == "array") return field_type::ARRAY;
    return field_type::UNKNOWN;
}

std::string field_type_to_string(field_type type) {
    switch (type) {
        case field_type::UINT64: return "uint64";
        case field_type::INT64: return "int64";
        case field_type::FLOAT64: return "float64";
        case field_type::BYTES: return "bytes";
        case field_type::BOOL: return "bool";
        case field_type::ARRAY: return "array";
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

        if (field_dtype.attr("kind").cast<std::string>() != "V") {
            details[name] = {
                .offset = py::cast<size_t>(desc[1]), 
                .size = py::cast<size_t>(field_dtype.attr("itemsize")), 
                .type = parse_field_type(field_dtype.attr("name").cast<std::string>())
            };
        } else {
            // field is an array
            details[name] = {
                .offset = py::cast<size_t>(desc[1]), 
                .size = py::cast<size_t>(field_dtype.attr("itemsize")), 
                .type = field_type::ARRAY
            };
        }
        
        if (details[name].type == field_type::UNKNOWN) {
            throw std::runtime_error("unknown field type (" + name + "): " + field_dtype.attr("name").cast<std::string>() + " of kind:" + field_dtype.attr("kind").cast<std::string>());
        }

#if DEBUG_OUTPUT
        std::cout << ">> field name: '" << name 
                  << "' offset: " << details[name].offset
                  << " size: " << details[name].size
                  << " type: " << field_type_to_string(details[name].type)
                  << std::endl;
#endif
    }
    return details;
}

void set_field_value(const rapidjson::Value& value, const char* field_name, field_type type, size_t size, char* field_ptr, bool quiet);
void set_field_value(const rapidjson::Value& value, const char* field_name, field_type type, size_t size, char* field_ptr, bool quiet)
{

    // don't rely on JSON data types. casts to bigger datatypes are dangerous
    switch (type)
    {
    case field_type::UINT64:
        *reinterpret_cast<uint64_t*>(field_ptr) = value.GetUint64();
        break;
    
    case field_type::INT64:
        *reinterpret_cast<int64_t*>(field_ptr) = value.GetInt64();
        break;
    
    case field_type::FLOAT64:
        *reinterpret_cast<double*>(field_ptr) = value.GetDouble();
        break;
    
    case field_type::BOOL:
        *reinterpret_cast<bool*>(field_ptr) = value.GetBool();
        break;
    
    case field_type::BYTES:
        if (value.IsString())
        {
            const char *str_value = value.GetString();
            size_t max_len = size - 1; // reserve space for null terminator
            size_t str_len = value.GetStringLength();
            // std::cout << "field: " << field_name << " bytes: " << value.GetString() << " max_len: " << max_len << " size: " << value.GetStringLength() << std::endl;
            if (str_len > max_len) {
                str_len = max_len;
            }
            std::memcpy(field_ptr, str_value, str_len);
            field_ptr[str_len] = '\0';
        }
        break;
    
    case field_type::UNKNOWN:
    default:
        if (!quiet) {
            std::cout << "ERROR: unknown type: " << value.GetType() << " for field: " << field_name << std::endl;
        }
        break;
    }
}

/// parse given mcap file with data in JSON format into a numpy structured array.
/// @param py_array numpy structured array, initialized in python
/// @param mcap_path path to the mcap file
/// @param topic only parse messages of this topic
/// @param quiet don't print anything
/// @return empty string on success, error message on failure
std::string parse_mcap(py::array& py_array, std::string mcap_path, std::string topic, uint64_t start_time_ns,
                       bool quiet)
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

    // check if we actually have a nested array
    bool has_nested_array = false;
    py::array py_array_nested;
    std::unordered_map<std::string, field_details> details_array;

    if (details.find("array") != details.end() && details["array"].type == field_type::ARRAY) {
        has_nested_array = true;
        py_array_nested = py_array[py::str("array")];
#if DEBUG_OUTPUT
        std::cout << "parsing py_array_nested.dtype(): " << py::str(py_array_nested.dtype()).cast<std::string>() << std::endl;
#endif
        details_array = get_field_details(py_array_nested.dtype());

#if DEBUG_OUTPUT
        std::cout << ">> py_array_nested.size(): " << py_array_nested.size() << std::endl;  // number of elements
        std::cout << ">> py_array_nested.itemsize(): " << py_array_nested.itemsize() << std::endl;  // bytes per element
        std::cout << ">> py_array_nested.nbytes(): " << py_array_nested.nbytes() << std::endl;
        std::cout << ">> py_array_nested.data(): " << py_array_nested.data() << std::endl;
        std::cout << ">> py_array_nested.dtype(): " << py::str(py_array_nested.dtype()).cast<std::string>() << std::endl;
        std::cout << ">> py_array_nested.ndim(): " << py_array_nested.ndim() << std::endl;  // number of dimensions
        std::cout << ">> py_array_nested.shape(): (";
        for (ssize_t i = 0; i < py_array_nested.ndim(); ++i) {
            std::cout << py_array_nested.shape(i);
            if (i < py_array_nested.ndim() - 1) std::cout << ", ";
        }
        std::cout << ")" << std::endl;
        std::cout << ">> py_array_nested.strides(): (";
        for (ssize_t i = 0; i < py_array_nested.ndim(); ++i) {
            std::cout << py_array_nested.strides(i);
            if (i < py_array_nested.ndim() - 1) std::cout << ", ";
        }
        std::cout << ")" << std::endl;
#endif
    }

    mcap::McapReader reader;
    {
        const auto res = reader.open(mcap_path);
        if (!res.ok()) {
            if (!quiet) {
                std::cerr << "ERROR: " << res.message << std::endl;
            }
            return "failed to open mcap file";
        }
    }

    // only load specified topic and use a specific start time
    mcap::ReadMessageOptions options;
    options.startTime = start_time_ns;
    options.topicFilter = [topic](const std::string_view _topic) {
        return _topic == topic;
    };

    mcap::ProblemCallback problemCallback = [quiet](const mcap::Status& status) {
        if (!quiet) {
            std::cerr << "ERROR parse-problem: " << status.message << std::endl;
        }
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
            if (!quiet) {
                std::cerr << "not a JSON message: " << it->channel->messageEncoding << std::endl;
            }
            continue;
        }

        rapidjson::Document doc;
        if (doc.Parse(reinterpret_cast<const char *>(it->message.data), it->message.dataSize).HasParseError())
        {
            if (!quiet) {
                std::cerr << "JSON parse error of message: " << it->message.data << std::endl;
            }
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
            // std::cout << "type: " << value.GetType() << " for field: " << field << std::endl;
            
            if (value.IsNull() || value.IsObject()) {
                // std::cout << "is null or object: " << field << std::endl;
                continue;
            }

            if (value.IsArray() && has_nested_array) {
                // check if "field" is in sub-array dtype
                std::unordered_map<std::string, field_details>::iterator details_array_it = details_array.find(field);
                if (details_array_it == details_array.end()) {
                    continue;
                }

                char* data_ptr_nested = row_ptr + details["array"].offset;
                size_t element_stride_nested = py_array_nested.strides(1);  // stride between elements in same row

                // add values to nested array
                size_t array_index = 0;
                for (auto& v : value.GetArray())
                {
                    // Safety check to prevent buffer overflow - check against number of columns, not rows
                    if (array_index >= static_cast<size_t>(py_array_nested.shape(1))) {
                        if (!quiet) {
                            std::cerr << "ERROR in message " << cnt << ": array (" << field << ") length " << value.Size() << " exceeds nested array column size " << py_array_nested.shape(1) << std::endl;
                        }
                        break;
                    } else {
                        // calculate pointer to current array element within the current row
                        char* row_ptr_nested = data_ptr_nested + (array_index * element_stride_nested);
                        
                        set_field_value(v, field, details_array_it->second.type, details_array_it->second.size, 
                                        row_ptr_nested + details_array_it->second.offset, quiet);
                    }

                    array_index++;
                }
                continue;
            }

            // check if "field" is in dtype
            std::unordered_map<std::string, field_details>::iterator details_it = details.find(field);
            if (details_it == details.end()) {
                continue;
            }
            
            set_field_value(value, field, details_it->second.type, details_it->second.size, 
                            row_ptr + details_it->second.offset, quiet);
        }

        cnt += 1;
        // print progress
        if (cnt % mod == 0) {
            int percent = static_cast<int>((static_cast<double>(cnt) / num_rows) * 100);
            if (!quiet) {
                std::cout << "\r>> Loading " << topic << ": " << percent << "%" << std::flush;
            }
        }
        if (cnt >= num_rows) {
            break;
        }
    }
    reader.close();
    if (!quiet) {
        std::cout << "\rLoading " << topic << ": 100% -> loaded " << cnt << " rows of " << num_rows << std::endl;
    }

#if DEBUG_OUTPUT
    std::clock_t end_cpu = std::clock();
    auto end_wall = std::chrono::high_resolution_clock::now();

    double wall_ms = std::chrono::duration<double>(end_wall - start_wall).count();
    double cpu_ms = (double)(end_cpu - start_cpu) / CLOCKS_PER_SEC;
    if (!quiet) {
        std::cout << ">> Wall time: " << wall_ms << " s" << std::endl;
        std::cout << ">> CPU time: " << cpu_ms << " s" << std::endl;
    }
#endif

    return "";
}

PYBIND11_MODULE(_core, m)
{
    m.doc() = "parse mcap file and decode JSON messages";

    m.def("parse_mcap", &parse_mcap, "parse mcap file and decode JSON messages",
          py::arg("py_array"), py::arg("mcap_path"), py::arg("topic"), py::arg("start_time_ns") = 0,
          py::arg("quiet") = false);

#ifdef VERSION_INFO
    m.attr("__version__") = MACRO_STRINGIFY(VERSION_INFO);
#else
    m.attr("__version__") = "dev";
#endif
}
