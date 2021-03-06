// Copyright (C) 2012-2013 Internet Systems Consortium, Inc. ("ISC")
//
// Permission to use, copy, modify, and/or distribute this software for any
// purpose with or without fee is hereby granted, provided that the above
// copyright notice and this permission notice appear in all copies.
//
// THE SOFTWARE IS PROVIDED "AS IS" AND ISC DISCLAIMS ALL WARRANTIES WITH
// REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
// AND FITNESS.  IN NO EVENT SHALL ISC BE LIABLE FOR ANY SPECIAL, DIRECT,
// INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
// LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE
// OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
// PERFORMANCE OF THIS SOFTWARE.

#ifndef OPTION_DEFINITION_H
#define OPTION_DEFINITION_H

#include <dhcp/option.h>
#include <dhcp/option_data_types.h>

#include <boost/multi_index/hashed_index.hpp>
#include <boost/multi_index/mem_fun.hpp>
#include <boost/multi_index/sequenced_index.hpp>
#include <boost/multi_index_container.hpp>
#include <boost/shared_ptr.hpp>

namespace isc {
namespace dhcp {

/// @brief Exception to be thrown when invalid option value has been
/// specified for a particular option definition.
class InvalidOptionValue : public Exception {
public:
    InvalidOptionValue(const char* file, size_t line, const char* what) :
        isc::Exception(file, line, what) { };
};

/// @brief Exception to be thrown when option definition is invalid.
class MalformedOptionDefinition : public Exception {
public:
    MalformedOptionDefinition(const char* file, size_t line, const char* what) :
        isc::Exception(file, line, what) { };
};

/// @brief Exception to be thrown when the particular option definition
/// duplicates existing option definition.
class DuplicateOptionDefinition : public Exception {
public:
    DuplicateOptionDefinition(const char* file, size_t line, const char* what) :
        isc::Exception(file, line, what) { };
};

/// @brief Forward declaration to OptionDefinition.
class OptionDefinition;

/// @brief Pointer to option definition object.
typedef boost::shared_ptr<OptionDefinition> OptionDefinitionPtr;

/// @brief Forward declaration to OptionInt.
///
/// This forward declaration is needed to access the OptionInt class without
/// having to include the option_int.h header file. It is required because
/// this header includes libdhcp++.h, and including option_int.h would cause
/// circular inclusion between libdhcp++.h, option_definition.h and
/// option6_int.h.
template<typename T>
class OptionInt;

/// @brief Forward declaration to OptionIntArray.
///
/// This forward declaration is needed to access the OptionIntArray class
/// without having to include the option_int_array.h header file. It is
/// required because this header includes libdhcp++.h, and including
/// option_int_array.h would cause circular inclusion between libdhcp++.h,
/// option_definition.h and option_int_array.h.
template<typename T>
class OptionIntArray;

/// @brief Base class representing a DHCP option definition.
///
/// This is a base class representing a DHCP option definition, which describes
/// the format of the option. In particular, it defines:
/// - option name,
/// - option code,
/// - data fields order and their types,
/// - sub options space that the particular option encapsulates.
///
/// The option type specifies the data type(s) which an option conveys.  If
/// this is a single value the option type points to the data type of the
/// value. For example, DHCPv6 option 8 comprises a two-byte option code, a
/// two-byte option length and two-byte field that carries a uint16 value
/// (RFC 3315 - http://ietf.org/rfc/rfc3315.txt).  In such a case, the option
/// type is defined as "uint16".
///
/// When the option has a more complex structure, the option type may be
/// defined as "array", "record" or even "array of records".
///
/// Array types should be used when the option contains multiple contiguous
/// data values of the same type laid. For example, DHCPv6 option 6 includes
/// multiple fields holding uint16 codes of requested DHCPv6 options (RFC 3315).
/// Such an option can be represented with this class by setting the option
/// type to "uint16" and the array indicator (array_type) to true.  The number
/// of elements in the array is effectively unlimited (although it is actually
/// limited by the maximal DHCPv6 option length).
///
/// Should the option comprise data fields of different types, the "record"
/// option type is used. In such cases the data field types within the record
/// are specified using \ref OptionDefinition::addRecordField.
///
/// When the OptionDefinition object has been sucessfully created, it can be
/// queried to return the appropriate option factory function for the specified
/// specified option format. There are a number of "standard" factory functions
/// that cover well known (common) formats.  If the particular format does not
/// match any common format the generic factory function is returned.
///
/// The following data type strings are supported:
/// - "empty" (option does not contain data fields)
/// - "boolean"
/// - "int8"
/// - "int16"
/// - "int32"
/// - "uint8"
/// - "uint16"
/// - "uint32"
/// - "ipv4-address" (IPv4 Address)
/// - "ipv6-address" (IPV6 Address)
/// - "string"
/// - "fqdn" (fully qualified name)
/// - "record" (set of data fields of different types)
///
/// @todo Extend the comment to describe "generic factories".
/// @todo Extend this class to use custom namespaces.
/// @todo Extend this class with more factory functions.
class OptionDefinition {
public:

    /// List of fields within the record.
    typedef std::vector<OptionDataType> RecordFieldsCollection;
    /// Const iterator for record data fields.
    typedef std::vector<OptionDataType>::const_iterator RecordFieldsConstIter;

    /// @brief Constructor.
    ///
    /// @param name option name.
    /// @param code option code.
    /// @param type option data type as string.
    /// @param array_type array indicator, if true it indicates that the
    /// option fields are the array.
    explicit OptionDefinition(const std::string& name,
                              const uint16_t code,
                              const std::string& type,
                              const bool array_type = false);

    /// @brief Constructor.
    ///
    /// @param name option name.
    /// @param code option code.
    /// @param type option data type.
    /// @param array_type array indicator, if true it indicates that the
    /// option fields are the array.
    explicit OptionDefinition(const std::string& name,
                              const uint16_t code,
                              const OptionDataType type,
                              const bool array_type = false);

    /// @brief Constructor.
    ///
    /// This constructor sets the name of the option space that is
    /// encapsulated by this option. The encapsulated option space
    /// identifies sub-options that are carried within this option.
    /// This constructor does not allow to set array indicator
    /// because options comprising an array of data fields must
    /// not be used with sub-options.
    ///
    /// @param name option name.
    /// @param code option code.
    /// @param type option data type given as string.
    /// @param encapsulated_space name of the option space being
    /// encapsulated by this option.
    explicit OptionDefinition(const std::string& name,
                              const uint16_t code,
                              const std::string& type,
                              const char* encapsulated_space);

    /// @brief Constructor.
    ///
    /// This constructor sets the name of the option space that is
    /// encapsulated by this option. The encapsulated option space
    /// identifies sub-options that are carried within this option.
    /// This constructor does not allow to set array indicator
    /// because options comprising an array of data fields must
    /// not be used with sub-options.
    ///
    /// @param name option name.
    /// @param code option code.
    /// @param type option data type.
    /// @param encapsulated_space name of the option space being
    /// encapsulated by this option.
    explicit OptionDefinition(const std::string& name,
                              const uint16_t code,
                              const OptionDataType type,
                              const char* encapsulated_space);


    /// @brief Adds data field to the record.
    ///
    /// @param data_type_name name of the data type for the field.
    ///
    /// @throw isc::InvalidOperation if option type is not set to RECORD_TYPE.
    /// @throw isc::BadValue if specified invalid data type.
    void addRecordField(const std::string& data_type_name);

    /// @brief Adds data field to the record.
    ///
    /// @param data_type data type for the field.
    ///
    /// @throw isc::InvalidOperation if option type is not set to RECORD_TYPE.
    /// @throw isc::BadValue if specified invalid data type.
    void addRecordField(const OptionDataType data_type);

    /// @brief Return array type indicator.
    ///
    /// The method returns the bool value to indicate whether the option is a
    /// a single value or an array of values.
    ///
    /// @return true if option comprises an array of values.
    bool getArrayType() const { return (array_type_); }

    /// @brief Return option code.
    ///
    /// @return option code.
    uint16_t getCode() const { return (code_); }

    /// @brief Return name of the encapsulated option space.
    ///
    /// @return name of the encapsulated option space.
    std::string getEncapsulatedSpace() const {
        return (encapsulated_space_);
    }

    /// @brief Return option name.
    ///
    /// @return option name.
    std::string getName() const { return (name_); }

    /// @brief Return list of record fields.
    ///
    /// @return list of record fields.
    const RecordFieldsCollection& getRecordFields() const { return (record_fields_); }

    /// @brief Return option data type.
    ///
    /// @return option data type.
    OptionDataType getType() const { return (type_); };

    /// @brief Check if the option definition is valid.
    ///
    /// Note that it is a responsibility of the code that created
    /// the OptionDefinition object to validate that it is valid.
    /// This function will not be called internally anywhere in this
    /// class to verify that the option definition is valid. Using
    /// invalid option definition to create an instance of the
    /// DHCP option leads to undefined behavior.
    ///
    /// @throw MalformedOptionDefinition option definition is invalid.
    void validate() const;

    /// @brief Check if specified format is IA_NA option format.
    ///
    /// @return true if specified format is IA_NA option format.
    bool haveIA6Format() const;

    /// @brief Check if specified format is IAADDR option format.
    ///
    /// @return true if specified format is IAADDR option format.
    bool haveIAAddr6Format() const;

    /// @brief Option factory.
    ///
    /// This function creates an instance of DHCP option using
    /// provided chunk of buffer. This function may be used to
    /// create option which is to be sent in the outgoing packet.
    ///
    /// @warning calling this function on invalid option definition
    /// yields undefined behavior. Use \ref validate to test that
    /// the option definition is valid.
    ///
    /// @param u option universe (V4 or V6).
    /// @param type option type.
    /// @param begin beginning of the option buffer.
    /// @param end end of the option buffer.
    ///
    /// @return instance of the DHCP option.
    /// @throw InvalidOptionValue if data for the option is invalid.
    OptionPtr optionFactory(Option::Universe u, uint16_t type,
                            OptionBufferConstIter begin,
                            OptionBufferConstIter end) const;

    /// @brief Option factory.
    ///
    /// This function creates an instance of DHCP option using
    /// whole provided buffer. This function may be used to
    /// create option which is to be sent in the outgoing packet.
    ///
    /// @warning calling this function on invalid option definition
    /// yields undefined behavior. Use \ref validate to test that
    /// the option definition is valid.
    ///
    /// @param u option universe (V4 or V6).
    /// @param type option type.
    /// @param buf option buffer.
    ///
    /// @return instance of the DHCP option.
    /// @throw InvalidOptionValue if data for the option is invalid.
    OptionPtr optionFactory(Option::Universe u, uint16_t type,
                            const OptionBuffer& buf = OptionBuffer()) const;

    /// @brief Option factory.
    ///
    /// This function creates an instance of DHCP option using the vector
    /// of strings which carry data values for option data fields.
    /// The order of values in the vector corresponds to the order of data
    /// fields in the option. The supplied string values are cast to
    /// their actual data types which are determined based on the
    /// option definition. If cast fails due to type mismatch, an exception
    /// is thrown. This factory function can be used to create option
    /// instance when user specified option value in the <b>comma separated
    /// values</b> format in the configuration database. Provided string
    /// must be tokenized into the vector of string values and this vector
    /// can be supplied to this function.
    ///
    /// @warning calling this function on invalid option definition
    /// yields undefined behavior. Use \ref validate to test that
    /// the option definition is valid.
    ///
    /// @param u option universe (V4 or V6).
    /// @param type option type.
    /// @param values a vector of values to be used to set data for an option.
    ///
    /// @return instance of the DHCP option.
    /// @throw InvalidOptionValue if data for the option is invalid.
    OptionPtr optionFactory(Option::Universe u, uint16_t type,
                            const std::vector<std::string>& values) const;

    /// @brief Factory to create option with address list.
    ///
    /// @param type option type.
    /// @param begin iterator pointing to the beginning of the buffer
    /// with a list of IPv4 addresses.
    /// @param end iterator pointing to the end of the buffer with
    /// a list of IPv4 addresses.
    ///
    /// @throw isc::OutOfRange if length of the provided option buffer
    /// is not multiple of IPV4 address length.
    static OptionPtr factoryAddrList4(uint16_t type,
                                      OptionBufferConstIter begin,
                                      OptionBufferConstIter end);

    /// @brief Factory to create option with address list.
    ///
    /// @param type option type.
    /// @param begin iterator pointing to the beginning of the buffer
    /// with a list of IPv6 addresses.
    /// @param end iterator pointing to the end of the buffer with
    /// a list of IPv6 addresses.
    ///
    /// @throw isc::OutOfaRange if length of provided option buffer
    /// is not multiple of IPV6 address length.
    static OptionPtr factoryAddrList6(uint16_t type,
                                      OptionBufferConstIter begin,
                                      OptionBufferConstIter end);

    /// @brief Empty option factory.
    ///
    /// @param u universe (V6 or V4).
    /// @param type option type.
    static OptionPtr factoryEmpty(Option::Universe u, uint16_t type);

    /// @brief Factory to create generic option.
    ///
    /// @param u universe (V6 or V4).
    /// @param type option type.
    /// @param begin iterator pointing to the beginning of the buffer.
    /// @param end iterator pointing to the end of the buffer.
    static OptionPtr factoryGeneric(Option::Universe u, uint16_t type,
                                    OptionBufferConstIter begin,
                                    OptionBufferConstIter end);

    /// @brief Factory for IA-type of option.
    ///
    /// @param type option type.
    /// @param begin iterator pointing to the beginning of the buffer.
    /// @param end iterator pointing to the end of the buffer.
    ///
    /// @throw isc::OutOfRange if provided option buffer is too short or
    /// too long. Expected size is 12 bytes.
    /// @throw isc::BadValue if specified universe value is not V6.
    static OptionPtr factoryIA6(uint16_t type,
                                OptionBufferConstIter begin,
                                OptionBufferConstIter end);

    /// @brief Factory for IAADDR-type of option.
    ///
    /// @param type option type.
    /// @param begin iterator pointing to the beginning of the buffer.
    /// @param end iterator pointing to the end of the buffer.
    ///
    /// @throw isc::OutOfRange if provided option buffer is too short or
    /// too long. Expected size is 24 bytes.
    /// @throw isc::BadValue if specified universe value is not V6.
    static OptionPtr factoryIAAddr6(uint16_t type,
                                    OptionBufferConstIter begin,
                                    OptionBufferConstIter end);

    /// @brief Factory function to create option with integer value.
    ///
    /// @param u universe (V4 or V6).
    /// @param type option type.
    /// @param begin iterator pointing to the beginning of the buffer.
    /// @param end iterator pointing to the end of the buffer.
    /// @tparam T type of the data field (must be one of the uintX_t or intX_t).
    ///
    /// @throw isc::OutOfRange if provided option buffer length is invalid.
    template<typename T>
    static OptionPtr factoryInteger(Option::Universe u, uint16_t type,
                                    OptionBufferConstIter begin,
                                    OptionBufferConstIter end) {
        OptionPtr option(new OptionInt<T>(u, type, begin, end));
        return (option);
    }

    /// @brief Factory function to create option with array of integer values.
    ///
    /// @param u universe (V4 or V6).
    /// @param type option type.
    /// @param begin iterator pointing to the beginning of the buffer.
    /// @param end iterator pointing to the end of the buffer.
    /// @tparam T type of the data field (must be one of the uintX_t or intX_t).
    ///
    /// @throw isc::OutOfRange if provided option buffer length is invalid.
    template<typename T>
    static OptionPtr factoryIntegerArray(Option::Universe u,
                                         uint16_t type,
                                         OptionBufferConstIter begin,
                                         OptionBufferConstIter end) {
        OptionPtr option(new OptionIntArray<T>(u, type, begin, end));
        return (option);
    }

private:

    /// @brief Check if specified option format is a record with 3 fields
    /// where first one is custom, and two others are uint32.
    ///
    /// This is a helper function for functions that detect IA_NA and IAAddr
    /// option formats.
    ///
    /// @param first_type type of the first data field.
    ///
    /// @return true if actual option format matches expected format.
    bool haveIAx6Format(const OptionDataType first_type) const;

    /// @brief Check if specified type matches option definition type.
    ///
    /// @return true if specified type matches option definition type.
    inline bool haveType(const OptionDataType type) const {
        return (type == type_);
    }

    /// @brief Perform lexical cast of the value and validate its range.
    ///
    /// This function performs lexical cast of a string value to integer
    /// or boolean value and checks if the resulting value is within a
    /// range of a target type. Note that range checks are not performed
    /// on boolean values. The target type should be one of the supported
    /// integer types or bool.
    ///
    /// @param value_str input value given as string.
    /// @tparam T target type for lexical cast.
    ///
    /// @return cast value.
    /// @throw BadDataTypeCast if cast was not successful.
    template<typename T>
    T lexicalCastWithRangeCheck(const std::string& value_str) const;

    /// @brief Write the string value into the provided buffer.
    ///
    /// This method writes the given value to the specified buffer.
    /// The provided string value may represent data of different types.
    /// The actual data type is specified with the second argument.
    /// Based on a value of this argument, this function will first
    /// try to cast the string value to the particular data type and
    /// if it is successful it will store the data in the buffer
    /// in a binary format.
    ///
    /// @param value string representation of the value to be written.
    /// @param type the actual data type to be stored.
    /// @param [in, out] buf buffer where the value is to be stored.
    ///
    /// @throw BadDataTypeCast if data write was unsuccessful.
    void writeToBuffer(const std::string& value, const OptionDataType type,
                       OptionBuffer& buf) const;

    /// @brief Sanity check universe value.
    ///
    /// @param expected_universe expected universe value.
    /// @param actual_universe actual universe value.
    ///
    /// @throw isc::BadValue if expected universe and actual universe don't match.
   static inline void sanityCheckUniverse(const Option::Universe expected_universe,
                                          const Option::Universe actual_universe);

    /// Option name.
    std::string name_;
    /// Option code.
    uint16_t code_;
    /// Option data type.
    OptionDataType type_;
    /// Indicates wheter option is a single value or array.
    bool array_type_;
    /// Name of the space being encapsulated by this option.
    std::string encapsulated_space_;
    /// Collection of data fields within the record.
    RecordFieldsCollection record_fields_;
};


/// @brief Multi index container for DHCP option definitions.
///
/// This container allows to search for DHCP option definition
/// using two indexes:
/// - sequenced: used to access elements in the order they have
/// been added to the container
/// - option code: used to search definitions of options
/// with a specified option code (aka option type).
/// Note that this container can hold multiple options with the
/// same code. For this reason, the latter index can be used to
/// obtain a range of options for a particular option code.
///
/// @todo: need an index to search options using option space name
/// once option spaces are implemented.
typedef boost::multi_index_container<
    // Container comprises elements of OptionDefinition type.
    OptionDefinitionPtr,
    // Here we start enumerating various indexes.
    boost::multi_index::indexed_by<
        // Sequenced index allows accessing elements in the same way
        // as elements in std::list. Sequenced is an index #0.
        boost::multi_index::sequenced<>,
        // Start definition of index #1.
        boost::multi_index::hashed_non_unique<
            // Use option type as the index key. The type is held
            // in OptionDefinition object so we have to call
            // OptionDefinition::getCode to retrieve this key
            // for each element. The option code is non-unique so
            // multiple elements with the same option code can
            // be returned by this index.
            boost::multi_index::const_mem_fun<
                OptionDefinition,
                uint16_t,
                &OptionDefinition::getCode
            >
        >
    >
> OptionDefContainer;

/// Pointer to an option definition container.
typedef boost::shared_ptr<OptionDefContainer> OptionDefContainerPtr;

/// Type of the index #1 - option type.
typedef OptionDefContainer::nth_index<1>::type OptionDefContainerTypeIndex;
/// Pair of iterators to represent the range of options definitions
///  having the same option type value. The first element in this pair
///  represents the beginning of the range, the second element
///  represents the end.
typedef std::pair<OptionDefContainerTypeIndex::const_iterator,
                  OptionDefContainerTypeIndex::const_iterator> OptionDefContainerTypeRange;


} // namespace isc::dhcp
} // namespace isc

#endif // OPTION_DEFINITION_H
