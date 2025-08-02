import Foundation

// MARK: - Validation Errors

enum ValidationError: LocalizedError {
    case emptyField(fieldName: String)
    case invalidFormat(fieldName: String, expectedFormat: String)
    case lengthExceeded(fieldName: String, maxLength: Int)
    case invalidURL
    case invalidEmail
    case invalidPort
    case outOfRange(fieldName: String, min: Any, max: Any)
    
    var errorDescription: String? {
        switch self {
        case .emptyField(let fieldName):
            return "\(fieldName) cannot be empty"
        case .invalidFormat(let fieldName, let expectedFormat):
            return "\(fieldName) must be in format: \(expectedFormat)"
        case .lengthExceeded(let fieldName, let maxLength):
            return "\(fieldName) must be less than \(maxLength) characters"
        case .invalidURL:
            return "Please enter a valid URL"
        case .invalidEmail:
            return "Please enter a valid email address"
        case .invalidPort:
            return "Port must be between 1 and 65535"
        case .outOfRange(let fieldName, let min, let max):
            return "\(fieldName) must be between \(min) and \(max)"
        }
    }
}

// MARK: - Validators

struct Validators {
    
    /// Validate that a string is not empty
    static func notEmpty(_ value: String, fieldName: String) throws {
        if value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            throw ValidationError.emptyField(fieldName: fieldName)
        }
    }
    
    /// Validate URL format
    static func url(_ value: String) throws {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        
        guard !trimmed.isEmpty else {
            throw ValidationError.emptyField(fieldName: "URL")
        }
        
        // Allow URLs without scheme for convenience
        let urlString = trimmed.hasPrefix("http://") || trimmed.hasPrefix("https://") || trimmed.hasPrefix("ws://") || trimmed.hasPrefix("wss://")
            ? trimmed
            : "http://\(trimmed)"
        
        guard let url = URL(string: urlString),
              url.host != nil else {
            throw ValidationError.invalidURL
        }
    }
    
    /// Validate email format
    static func email(_ value: String) throws {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        
        guard !trimmed.isEmpty else {
            throw ValidationError.emptyField(fieldName: "Email")
        }
        
        let emailRegex = "[A-Z0-9a-z._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,64}"
        let emailPredicate = NSPredicate(format:"SELF MATCHES %@", emailRegex)
        
        guard emailPredicate.evaluate(with: trimmed) else {
            throw ValidationError.invalidEmail
        }
    }
    
    /// Validate port number
    static func port(_ value: Int) throws {
        guard (1...65535).contains(value) else {
            throw ValidationError.invalidPort
        }
    }
    
    /// Validate string length
    static func maxLength(_ value: String, maxLength: Int, fieldName: String) throws {
        if value.count > maxLength {
            throw ValidationError.lengthExceeded(fieldName: fieldName, maxLength: maxLength)
        }
    }
    
    /// Validate numeric range
    static func range<T: Comparable>(_ value: T, min: T, max: T, fieldName: String) throws {
        guard value >= min && value <= max else {
            throw ValidationError.outOfRange(fieldName: fieldName, min: min, max: max)
        }
    }
}

// MARK: - Form Validation

struct FormValidator {
    private var errors: [String: ValidationError] = [:]
    
    mutating func validate(field: String, validation: () throws -> Void) {
        do {
            try validation()
            errors.removeValue(forKey: field)
        } catch let error as ValidationError {
            errors[field] = error
        } catch {
            // Handle unexpected errors
            errors[field] = ValidationError.invalidFormat(fieldName: field, expectedFormat: "valid input")
        }
    }
    
    var isValid: Bool {
        errors.isEmpty
    }
    
    func error(for field: String) -> ValidationError? {
        errors[field]
    }
    
    var allErrors: [ValidationError] {
        Array(errors.values)
    }
}

// MARK: - SwiftUI Integration

import SwiftUI

struct ValidationModifier: ViewModifier {
    let field: String
    let validation: () throws -> Void
    @Binding var errorMessage: String?
    
    func body(content: Content) -> some View {
        content
            .onChange(of: field) { _, _ in
                do {
                    try validation()
                    errorMessage = nil
                } catch let error as ValidationError {
                    errorMessage = error.errorDescription
                } catch {
                    errorMessage = "Invalid input"
                }
            }
    }
}

extension View {
    func validate(
        field: String,
        errorMessage: Binding<String?>,
        validation: @escaping () throws -> Void
    ) -> some View {
        modifier(ValidationModifier(
            field: field,
            validation: validation,
            errorMessage: errorMessage
        ))
    }
}