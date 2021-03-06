// Copyright (C) 2011  Internet Systems Consortium, Inc. ("ISC")
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

#ifndef MESSAGE_EXCEPTION_H
#define MESSAGE_EXCEPTION_H

#include <exceptions/exceptions.h>
#include <log/message_types.h>

#include <stdexcept>
#include <string>
#include <vector>

#include <boost/lexical_cast.hpp>

namespace isc {
namespace log {

/// \brief Message Exception
///
/// Used in the message reader, this simple exception class allows a message
/// code and its arguments to be encapsulated in an exception and thrown
/// up the stack.

class MessageException : public isc::Exception {
public:

    /// \brief Constructor
    ///
    /// \param file Filename where the exception occurred.
    /// \param line Line where exception occurred.
    /// \param what Text description of the problem.
    /// \param id Message identification.
    /// \param lineno Line number on which error occurred (if > 0).
    MessageException(const char* file, size_t line, const char* what,
                     MessageID id, int lineno)
        : isc::Exception(file, line, what), id_(id), lineno_(lineno)
    {
        if (lineno_ > 0) {
            args_.push_back(boost::lexical_cast<std::string>(lineno));
        }
    }

    /// \brief Constructor
    ///
    /// \param file Filename where the exception occurred.
    /// \param line Line where exception occurred.
    /// \param what Text description of the problem.
    /// \param id Message identification.
    /// \param arg1 First message argument.
    /// \param lineno Line number on which error occurred (if > 0).
    MessageException(const char* file, size_t line, const char* what,
                     MessageID id, const std::string& arg1, int lineno)
        : isc::Exception(file, line, what), id_(id)
    {
        if (lineno > 0) {
            args_.push_back(boost::lexical_cast<std::string>(lineno));
        }
        args_.push_back(arg1);
    }

    /// \brief Constructor
    ///
    /// \param file Filename where the exception occurred.
    /// \param line Line where exception occurred.
    /// \param what Text description of the problem.
    /// \param id Message identification.
    /// \param arg1 First message argument.
    /// \param arg2 Second message argument.
    /// \param lineno Line number on which error occurred (if > 0).
    MessageException(const char* file, size_t line, const char *what,
                     MessageID id, const std::string& arg1,
                     const std::string& arg2, int lineno)
        : isc::Exception(file, line, what), id_(id)
    {
        if (lineno > 0) {
            args_.push_back(boost::lexical_cast<std::string>(lineno));
        }
        args_.push_back(arg1);
        args_.push_back(arg2);
    }

    /// \brief Destructor
    ~MessageException() throw() {}

    /// \brief Return Message ID
    ///
    /// \return Message identification
    MessageID id() const {
        return id_;
    }

    /// \brief Return Arguments
    ///
    /// \return Exception Arguments
    std::vector<std::string> arguments() const {
        return (args_);
    }

private:
    MessageID                   id_;        // Exception ID
    std::vector<std::string>    args_;      // Exception arguments
    int lineno_;
};

} // namespace log
} // namespace isc

#endif // MESSAGE_EXCEPTION_H
